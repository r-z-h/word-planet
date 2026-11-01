#requires -Version 5.1
<#
  Word Planet - public demo tunnel
  Cloudflare quick tunnel  +  local Basic Auth "password gate"

      browser --https--> trycloudflare --http--> 127.0.0.1:8080 (gate) --> 127.0.0.1:5173 (vite)
                                                                     \--> /api proxy --> 127.0.0.1:8000

  Usage (from project root):
    .\tools\tunnel.ps1 start     启动口令门 + cloudflared，打印公网 URL 和登录口令
    .\tools\tunnel.ps1 stop      停止口令门 + cloudflared（不影响开发栈）
    .\tools\tunnel.ps1 restart   等价于 stop + start（公网 URL 会变）
    .\tools\tunnel.ps1 status    查看状态 / URL / 登录口令
    .\tools\tunnel.ps1 url       只打印当前公网 URL（脚本/其它工具调用方便）

  落盘位置（均在 .run/ 下，已 git-ignored）：
    .run\tunnel-credentials.json      用户名/口令 + createdAt（删除该文件即可轮换）
    .run\tunnel-gate.pid.json         口令门进程 { pid, startedAt, port }
    .run\tunnel-cloudflared.pid.json  cloudflared 进程 { pid, startedAt, metricsPort }
    .run\tunnel-state.json            最近一次 start 结果 { publicUrl, startedAt, ... }
    .run\tunnel-url.txt               纯文本公网 URL（供外部脚本读取）

  日志：.logs\cf.err.log / cf.out.log / auth-proxy.out.log / auth-proxy.err.log
          （每次 start 会轮换旧日志到 *.prev.log，避免读到上一次的旧 URL）

  公网 URL 解析顺序：先读 cloudflared 自身的 metrics（authoritative，永远对应当前进程），
  再退回解析 cf.err.log。这样即使旧日志残留也不会误报上一个隧道地址。
#>

param(
    [Parameter(Position = 0)]
    [ValidateSet('start', 'stop', 'restart', 'status', 'url')]
    [string]$Action = 'status'
)

$ErrorActionPreference = 'Continue'
$ScriptVersion = '2.0'

# ---------------- paths ----------------
$ToolsDir    = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root        = Split-Path -Parent $ToolsDir
$LogDir      = Join-Path $Root '.logs'
$RunDir      = Join-Path $Root '.run'
$CredFile    = Join-Path $RunDir 'tunnel-credentials.json'
$StateFile   = Join-Path $RunDir 'tunnel-state.json'
$CfPidFile   = Join-Path $RunDir 'tunnel-cloudflared.pid.json'
$GatePidFile = Join-Path $RunDir 'tunnel-gate.pid.json'
$UrlFile     = Join-Path $RunDir 'tunnel-url.txt'
$ProxyScript = Join-Path $ToolsDir 'auth-proxy.mjs'
$Cloudflared = Join-Path $ToolsDir 'bin\cloudflared.exe'

$FrontendPort = 5173
$BackendPort  = 8000
$GatePort     = 8080
$CfMetrics    = 20242

$CfErr    = Join-Path $LogDir 'cf.err.log'
$CfOut    = Join-Path $LogDir 'cf.out.log'
$ProxyOut = Join-Path $LogDir 'auth-proxy.out.log'
$ProxyErr = Join-Path $LogDir 'auth-proxy.err.log'

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
New-Item -ItemType Directory -Force -Path $RunDir | Out-Null

# ---------------- helpers ----------------
# 用 TCP 连接判断端口（比 Get-NetTCPConnection 在各种环境下更可靠）
function Test-Port($port) {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $c.Connect('127.0.0.1', [int]$port)
        $ok = $c.Connected
        $c.Close()
        return [bool]$ok
    } catch { return $false }
}
# 从 netstat 反查监听该端口的进程号
function Get-PortPid($port) {
    $lines = netstat -ano | Where-Object { $_ -match 'LISTENING' -and $_ -match ":$port\s" }
    foreach ($l in $lines) { if ($l -match '\s+(\d+)\s*$') { return [int]$Matches[1] } }
    return $null
}
function Test-Alive($procId) {
    if (-not $procId) { return $false }
    try { Get-Process -Id ([int]$procId) -ErrorAction Stop | Out-Null; return $true } catch { return $false }
}
# 取进程信息；跨用户/提权进程可能 Access denied，此时返回 $null（不抛出）
function Get-ProcInfo($procId) {
    if (-not $procId) { return $null }
    try { return (Get-Process -Id ([int]$procId) -ErrorAction Stop) } catch { return $null }
}
# 校验某 pid 是否仍是「我们记下的那个进程」：名字匹配 + 启动时间不早于记录（防 PID 复用）
function Test-OwnedProcess($procId, $expectedName, $recordedStart) {
    $p = Get-ProcInfo $procId
    if (-not $p) {
        # 看不到进程（其它用户/提权）时无法确认身份，交给端口探测兜底
        return $false
    }
    if ($expectedName -and $p.ProcessName -ne $expectedName) { return $false }
    if ($recordedStart) {
        try {
            $rec = [datetime]$recordedStart
            if ($p.StartTime -lt $rec.AddSeconds(-2)) { return $false }
        } catch { }
    }
    return $true
}
function Stop-ByPid($procId) {
    if (-not $procId) { return $false }
    try { Stop-Process -Id ([int]$procId) -Force -ErrorAction Stop; return $true } catch { return $false }
}

# ---- JSON 读写（原子写：先写 .tmp 再替换，避免半截文件）----
function Write-JsonAtomic($obj, $path) {
    $tmp = "$path.tmp"
    $obj | ConvertTo-Json -Depth 6 | Set-Content -Path $tmp -Encoding UTF8
    Move-Item -Path $tmp -Destination $path -Force
}
function Read-JsonSafe($path) {
    if (-not (Test-Path $path)) { return $null }
    try { return (Get-Content $path -Raw -Encoding UTF8 | ConvertFrom-Json) } catch { return $null }
}

# ---- cloudflared metrics：权威来源，永远反映「当前进程」服务的 hostname ----
function Get-MetricsText($port) {
    try {
        $r = Invoke-WebRequest -UseBasicParsing -Uri ("http://127.0.0.1:{0}/metrics" -f $port) -TimeoutSec 3
        return [string]$r.Content
    } catch { return $null }
}
function Get-UrlFromMetrics($port) {
    $text = Get-MetricsText $port
    if (-not $text) { return $null }
    $m = [regex]::Matches($text, 'userHostname="(https://[A-Za-z0-9-]+\.trycloudflare\.com)"')
    if ($m.Count -gt 0) { return $m[$m.Count - 1].Groups[1].Value }
    return $null
}
function Get-UrlFromLog($path) {
    if (-not (Test-Path $path)) { return $null }
    $hits = Select-String -Path $path -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -AllMatches -ErrorAction SilentlyContinue |
            ForEach-Object { $_.Matches } | ForEach-Object { $_.Value }
    if ($hits) { return ($hits | Select-Object -Last 1) }
    return $null
}
# 公网 URL：先 metrics，再日志兜底
function Get-PublicUrl {
    $u = Get-UrlFromMetrics $CfMetrics
    if ($u) { return $u }
    return (Get-UrlFromLog $CfErr)
}

# ---- 口令 ----
function New-RandomPassword {
    $chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789'
    $bytes = New-Object 'System.Byte[]' 16
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $sb = New-Object System.Text.StringBuilder
    foreach ($b in $bytes) { [void]$sb.Append($chars[$b % $chars.Length]) }
    return $sb.ToString()
}
function Get-Creds {
    $c = Read-JsonSafe $CredFile
    if ($c -and $c.user -and $c.pass) { return $c }
    $cred = [pscustomobject]@{
        v         = 1
        user      = 'family'
        pass      = (New-RandomPassword)
        createdAt = (Get-Date).ToString('o')
    }
    Write-JsonAtomic $cred $CredFile
    Write-Host ("  [i] 已生成新口令并保存到 .run\tunnel-credentials.json")
    return $cred
}

# ---- 日志轮换：保留一份 .prev，主日志清空，避免旧 URL 污染解析 ----
function Rotate-Log($path) {
    if (Test-Path $path) {
        Move-Item -Path $path -Destination "$path.prev" -Force -ErrorAction SilentlyContinue
    }
}

# ---- 安全自检：从公网访问应返回 401（口令门生效）；200 说明绕过了口令门 ----
function Test-GateEnforced($url) {
    $curl = (Get-Command curl.exe -ErrorAction SilentlyContinue)
    if (-not $curl) { return $null }
    try {
        $code = & $curl.Source -s -o 'NUL' -w '%{http_code}' --max-time 12 $url 2>$null
        if ($code -eq '000') { return $null }   # 000 = 连不上/DNS 受限，无法自检
        return [string]$code
    } catch { return $null }
}

# 检测非本脚本启动的 cloudflared（例如遗留的、绕过 8080 的直连隧道）
function Find-StrayCloudflared {
    $strays = @()
    $ours = $null
    $rec = Read-JsonSafe $CfPidFile
    if ($rec -and $rec.pid) { $ours = [int]$rec.pid }
    # 监听我们 metrics 端口的进程，视为「我们自己的」
    $metricsPid = Get-PortPid $CfMetrics
    $owned = @()
    if ($ours) { $owned += $ours }
    if ($metricsPid) { $owned += [int]$metricsPid }
    # 可见的 cloudflared 进程
    try {
        Get-Process -Name cloudflared -ErrorAction SilentlyContinue | ForEach-Object {
            if ($owned -contains $_.Id) { return }
            # 本脚本的 cloudflared 应带 --metrics 20242；看得到命令行就据此区分
            $cmd = $null
            try { $cmd = $_.CommandLine } catch { }
            if (-not $cmd -or $cmd -notmatch '--metrics\s+127\.0\.0\.1:20242') {
                $strays += ("PID {0} (start {1})" -f $_.Id, $_.StartTime)
            }
        }
    } catch { }
    # 已知遗留指标端口 20241（历史遗留直连隧道常用）
    if ((Test-Port 20241)) {
        $p = Get-PortPid 20241
        if ($p -and ($owned -notcontains [int]$p)) { $strays += ("PID {0} (metrics 20241)" -f $p) }
    }
    return $strays
}

function Write-State($url, $gatePid, $cfPid) {
    $state = [pscustomobject]@{
        v          = 1
        version    = $ScriptVersion
        publicUrl  = $url
        startedAt  = (Get-Date).ToString('o')
        gatePid    = $gatePid
        cfPid      = $cfPid
        gatePort   = $GatePort
        metricsPort = $CfMetrics
    }
    Write-JsonAtomic $state $StateFile
    if ($url) { Set-Content -Path $UrlFile -Value $url -Encoding UTF8 }
    else { Remove-Item $UrlFile -Force -ErrorAction SilentlyContinue }
}

# ---------------- actions ----------------
function Do-Start {
    Write-Host ''
    Write-Host '=== public demo tunnel: start ==='

    if (-not (Test-Port $FrontendPort)) {
        Write-Host '  [!] 前端 5173 没在运行，请先启动开发栈：'
        Write-Host '        .\dev.ps1 start'
        Write-Host '      然后再运行：.\tools\tunnel.ps1 start'
        return
    }
    if (-not (Test-Port $BackendPort)) {
        Write-Host '  [!] 后端 8000 没在监听，页面能开但接口会报错'
    }
    if (-not (Test-Path $Cloudflared)) {
        Write-Host ("  [X] 找不到 cloudflared：{0}" -f $Cloudflared)
        return
    }

    # 遗留/越权 cloudflared 检查（只告警，绝不擅自杀别的进程）
    $strays = Find-StrayCloudflared
    if ($strays.Count -gt 0) {
        Write-Host '  [!] 发现非本脚本的 cloudflared（可能绕过口令门，请排查）：'
        foreach ($s in $strays) { Write-Host ("        - {0}" -f $s) }
        Write-Host '      确认后可 taskkill /F /PID <pid>（提权）清理；本脚本不会自动杀它。'
    }

    $cred = Get-Creds

    # ---- 口令门 ----
    $gatePid = $null
    $gateRec = Read-JsonSafe $GatePidFile
    if ($gateRec -and (Test-OwnedProcess $gateRec.pid 'node' $gateRec.startedAt) -and (Test-Port $GatePort)) {
        $gatePid = [int]$gateRec.pid
        Write-Host ("  [OK] 口令门已在运行 (8080, PID {0})" -f $gatePid)
    } elseif (Test-Port $GatePort) {
        # 端口被占但不是我们记录的进程：尝试按端口认领
        $p = Get-PortPid $GatePort
        $pi = Get-ProcInfo $p
        if ($pi -and $pi.ProcessName -eq 'node') {
            $gatePid = $p
            Write-JsonAtomic ([pscustomobject]@{ pid = $p; startedAt = $pi.StartTime.ToString('o'); port = $GatePort }) $GatePidFile
            Write-Host ("  [i] 沿用已在 8080 监听的 node 进程 PID {0}（若口令不一致请先 stop 再 start 以同步）" -f $p)
        } else {
            Write-Host '  [X] 端口 8080 被非 node 进程占用，无法启动口令门。'
            return
        }
    } else {
        Write-Host '  启动口令门 127.0.0.1:8080 ...'
        $env:WP_PROXY_USER    = $cred.user
        $env:WP_PROXY_PASS    = $cred.pass
        $env:WP_PROXY_PORT    = "$GatePort"
        $env:WP_PROXY_UPSTREAM = "$FrontendPort"
        Rotate-Log $ProxyOut; Rotate-Log $ProxyErr
        $nodeExe = (Get-Command node -ErrorAction SilentlyContinue).Source
        if (-not $nodeExe) { $nodeExe = 'node' }
        $gp = Start-Process -FilePath $nodeExe -ArgumentList ('"{0}"' -f $ProxyScript) -WorkingDirectory $Root `
            -RedirectStandardOutput $ProxyOut -RedirectStandardError $ProxyErr -WindowStyle Hidden -PassThru
        $gatePid = $gp.Id
        Write-JsonAtomic ([pscustomobject]@{ pid = $gp.Id; startedAt = $gp.StartTime.ToString('o'); port = $GatePort }) $GatePidFile
        $ok = $false
        for ($i = 0; $i -lt 40; $i++) { if (Test-Port $GatePort) { $ok = $true; break }; Start-Sleep -Milliseconds 250 }
        if (-not $ok) {
            Write-Host '  [X] 口令门启动失败，见 .logs\auth-proxy.err.log'
            if (Test-Path $ProxyErr) { Get-Content $ProxyErr -Tail 10 }
            return
        }
        Write-Host '  [OK] 口令门 http://127.0.0.1:8080'
    }

    # ---- cloudflared ----
    $cfPid = $null
    $cfRec = Read-JsonSafe $CfPidFile
    $aliveFromFile = $false
    if ($cfRec -and $cfRec.pid) {
        if ((Test-OwnedProcess $cfRec.pid 'cloudflared' $cfRec.startedAt) -or ((Test-Port $CfMetrics) -and $cfRec.pid)) {
            $cfPid = [int]$cfRec.pid
            $aliveFromFile = Test-Port $CfMetrics
        }
    }
    if (-not $aliveFromFile -and (Test-Port $CfMetrics)) {
        # 有 cloudflared 在 20242 上但没记录/记录失效：按端口认领
        $p = Get-PortPid $CfMetrics
        $pi = Get-ProcInfo $p
        if ($pi -and $pi.ProcessName -eq 'cloudflared') {
            $cfPid = $p
            Write-JsonAtomic ([pscustomobject]@{ pid = $p; startedAt = $pi.StartTime.ToString('o'); metricsPort = $CfMetrics }) $CfPidFile
            $aliveFromFile = $true
            Write-Host ("  [i] 沿用已在 20242 的 cloudflared PID {0}" -f $p)
        }
    }

    if ($aliveFromFile) {
        Write-Host ("  [i] cloudflared 已在运行 (PID {0})，跳过启动" -f $cfPid)
    } else {
        Write-Host '  启动 cloudflared 临时隧道 ...'
        Rotate-Log $CfErr; Rotate-Log $CfOut
        $cp = Start-Process -FilePath $Cloudflared `
            -ArgumentList 'tunnel', '--url', "http://127.0.0.1:$GatePort", '--protocol', 'http2', '--no-autoupdate', '--metrics', "127.0.0.1:$CfMetrics" `
            -WorkingDirectory $Root `
            -RedirectStandardOutput $CfOut -RedirectStandardError $CfErr -WindowStyle Hidden -PassThru
        $cfPid = $cp.Id
        Write-JsonAtomic ([pscustomobject]@{ pid = $cp.Id; startedAt = $cp.StartTime.ToString('o'); metricsPort = $CfMetrics }) $CfPidFile
    }

    # ---- 等待公网 URL（metrics 优先，日志兜底）----
    $url = $null
    for ($i = 0; $i -lt 120; $i++) {
        $url = Get-UrlFromMetrics $CfMetrics
        if (-not $url) { $url = Get-UrlFromLog $CfErr }
        if ($url) { break }
        Start-Sleep -Milliseconds 500
    }

    Write-State $url $gatePid $cfPid

    Write-Host ''
    if ($url) {
        Write-Host '  ------------------------------------------------------------' -ForegroundColor Green
        Write-Host '  PUBLIC URL : ' -NoNewline; Write-Host $url -ForegroundColor Cyan
        Write-Host "  USERNAME   : $($cred.user)"
        Write-Host "  PASSWORD   : $($cred.pass)"
        Write-Host '  ------------------------------------------------------------' -ForegroundColor Green
        Write-Host ("  gate PID {0} / cloudflared PID {1}（已写入 .run\*.pid.json）" -f $gatePid, $cfPid)

        # 安全自检：公网应被 401 拦下
        Write-Host '  自检公网口令门（应返回 401）...' -NoNewline
        $code = Test-GateEnforced $url
        if ($code -eq '401') {
            Write-Host ' [OK] 401 口令门生效' -ForegroundColor Green
        } elseif ($code -eq '200') {
            Write-Host ' [X] 200：口令门被绕过！请立即排查' -ForegroundColor Red
        } elseif ($code) {
            Write-Host (" [i] 返回 {0}（非预期，稍后手动访问确认）" -f $code)
        } else {
            Write-Host ' [i] 无法自检（无 curl.exe 或网络超时）'
        }

        Write-Host '  把「链接 + 用户名 + 密码」一起发给对方；对方打开链接会先看到口令登录页。'
        Write-Host '  注意：临时隧道每次重启链接都会变；Web 推送在此模式下不可用。'
    } else {
        Write-Host '  [!] 还没拿到公网链接。.logs\cf.err.log 末尾：'
        if (Test-Path $CfErr) { Get-Content $CfErr -Tail 20 }
    }
    Write-Host ''
}

function Do-Stop {
    Write-Host ''
    Write-Host '=== public demo tunnel: stop ==='
    # cloudflared
    $cfRec = Read-JsonSafe $CfPidFile
    $stopped = $false
    if ($cfRec -and $cfRec.pid) {
        if (Stop-ByPid $cfRec.pid) { $stopped = $true }
    }
    if (-not $stopped) {
        $p = Get-PortPid $CfMetrics
        if ($p) { Stop-ByPid $p | Out-Null; $stopped = $true }
    }
    Remove-Item $CfPidFile -Force -ErrorAction SilentlyContinue
    Write-Host '  [OK] cloudflared 已停止'

    # gate
    $gateRec = Read-JsonSafe $GatePidFile
    if ($gateRec -and $gateRec.pid) { Stop-ByPid $gateRec.pid | Out-Null }
    Stop-ByPid (Get-PortPid $GatePort) | Out-Null
    Remove-Item $GatePidFile -Force -ErrorAction SilentlyContinue
    Write-Host '  [OK] 口令门已停止'

    Remove-Item $StateFile -Force -ErrorAction SilentlyContinue
    Remove-Item $UrlFile -Force -ErrorAction SilentlyContinue
    Write-Host '  （开发栈保持运行；要停开发栈用 .\dev.ps1 stop）'
    Write-Host ''
}

function Do-Status {
    Write-Host ''
    Write-Host ("Word Planet tunnel status  (script v{0})" -f $ScriptVersion)
    Write-Host '----------------------------------------'
    $cred = Read-JsonSafe $CredFile
    $cfRec = Read-JsonSafe $CfPidFile
    $gateRec = Read-JsonSafe $GatePidFile
    $state = Read-JsonSafe $StateFile

    $cfAlive = $false
    if ($cfRec -and $cfRec.pid) { $cfAlive = Test-OwnedProcess $cfRec.pid 'cloudflared' $cfRec.startedAt }
    if (-not $cfAlive -and (Test-Port $CfMetrics)) { $cfAlive = $true }

    Write-Host ("  frontend 5173 : {0}" -f $(if (Test-Port $FrontendPort) { 'RUNNING' } else { 'STOPPED' }))
    Write-Host ("  backend  8000 : {0}" -f $(if (Test-Port $BackendPort) { 'RUNNING' } else { 'STOPPED' }))
    Write-Host ("  auth gate 8080: {0}{1}" -f $(if (Test-Port $GatePort) { 'RUNNING' } else { 'STOPPED' }), $(if ($gateRec -and $gateRec.pid) { " (PID $($gateRec.pid))" } else { '' }))
    Write-Host ("  cloudflared   : {0}{1}" -f $(if ($cfAlive) { 'RUNNING' } else { 'STOPPED' }), $(if ($cfRec -and $cfRec.pid) { " (PID $($cfRec.pid))" } else { '' }))

    if ($cfAlive) {
        $url = Get-UrlFromMetrics $CfMetrics
        $src = 'metrics'
        if (-not $url) { $url = Get-UrlFromLog $CfErr; $src = 'log' }
        if ($url) { Write-Host ("  public url    : {0}  [{1}]" -f $url, $src) }
        if ($state -and $state.publicUrl -and $url -and ($state.publicUrl -ne $url)) {
            Write-Host ("  [!] 状态文件里的 URL 与当前进程不一致：state={0}" -f $state.publicUrl) -ForegroundColor Yellow
        }
    } else {
        $last = $null
        if ($state -and $state.publicUrl) { $last = $state.publicUrl } else { $last = Get-UrlFromLog $CfErr }
        Write-Host '  public url    : (未运行)'
        if ($last) { Write-Host ("  last url      : {0}  (已停止，链接可能已失效)" -f $last) -ForegroundColor DarkGray }
    }
    if ($cred) { Write-Host ("  login         : {0} / {1}  (.run\tunnel-credentials.json)" -f $cred.user, $cred.pass) }
    else { Write-Host '  login         : (未生成，首次 start 时会创建)' }

    $strays = Find-StrayCloudflared
    if ($strays.Count -gt 0) {
        Write-Host '  [!] 非本脚本的 cloudflared（可能绕过口令门）：' -ForegroundColor Yellow
        foreach ($s in $strays) { Write-Host ("        - {0}" -f $s) }
    }
    Write-Host ''
}

function Do-Url {
    $rec = Read-JsonSafe $CfPidFile
    $alive = $false
    if ($rec -and $rec.pid) { $alive = Test-OwnedProcess $rec.pid 'cloudflared' $rec.startedAt }
    if (-not $alive -and (Test-Port $CfMetrics)) { $alive = $true }
    if (-not $alive) { exit 1 }
    $url = Get-UrlFromMetrics $CfMetrics
    if (-not $url) { $url = Get-UrlFromLog $CfErr }
    if ($url) { Write-Output $url } else { exit 1 }
}

switch ($Action) {
    'start'   { Do-Start }
    'stop'    { Do-Stop }
    'restart' { Do-Stop; Do-Start }
    'status'  { Do-Status }
    'url'     { Do-Url }
}
