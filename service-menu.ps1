#requires -Version 5.1
# Word Planet 统一「服务管理」菜单（唯一入口）。
# 实际启停逻辑在 dev.ps1；本脚本负责菜单，以及“打开网页 / 查看报错 / 环境检查”。
# 双击 服务管理.bat（无参=交互菜单）；也可 -MenuAction status|errors|doctor|open 供脚本调用。
param(
    [ValidateSet('menu', 'status', 'errors', 'doctor', 'open')]
    [string]$MenuAction = 'menu'
)
$ErrorActionPreference = 'Continue'

$Root   = Split-Path -Parent $MyInvocation.MyCommand.Path
$Dev    = Join-Path $Root 'dev.ps1'
$LogDir = Join-Path $Root '.logs'
$PgLog  = 'D:\PostgreSQL\log\server.log'

function Show-Banner {
    Write-Host ''
    Write-Host '  ============================================' -ForegroundColor Cyan
    Write-Host '              Word Planet 服务管理' -ForegroundColor Cyan
    Write-Host '  ============================================' -ForegroundColor Cyan
    Write-Host '   1 启动服务      2 停止服务      3 重启服务'
    Write-Host '   4 服务状态      5 打开网页      6 查看报错'
    Write-Host '   7 环境检查      0 退出'
    Write-Host '  --------------------------------------------' -ForegroundColor DarkGray
}

function Pause-Menu { Write-Host ''; [void](Read-Host '  按回车返回菜单') }

function Invoke-OpenWeb {
    $url = 'http://localhost:5273'
    try { Start-Process $url; Write-Host ('  已打开 ' + $url) -ForegroundColor Green }
    catch { Write-Host ('  打开失败: ' + $_.Exception.Message) -ForegroundColor Red }
}

function Get-FilteredLog($path, $maxLines = 200, $keep = 25) {
    if (-not (Test-Path -LiteralPath $path)) { return @() }
    $lines = Get-Content -LiteralPath $path -Tail $maxLines -ErrorAction SilentlyContinue
    $errs = $lines |
        Where-Object { $_ -match '(?i)error|exception|traceback|fail|refused|timeout|unhandled|\s[45]\d\d\b' } |
        Where-Object { -not ($_ -match 'HTTP/1\.[01]"\s+[23]\d\d') }
    if ($errs -and $errs.Count -gt $keep) { $errs = $errs[-$keep..-1] }
    return $errs
}

function Show-Errors {
    Write-Host ''
    Write-Host '  === 查看报错（汇总所有来源，已滤掉正常访问日志） ===' -ForegroundColor Cyan
    $sources = @(
        @{ Name = '后端 out'; Path = (Join-Path $LogDir 'backend.out.log') },
        @{ Name = '后端 err'; Path = (Join-Path $LogDir 'backend.err.log') },
        @{ Name = '前端 out'; Path = (Join-Path $LogDir 'frontend.out.log') },
        @{ Name = '前端 err'; Path = (Join-Path $LogDir 'frontend.err.log') },
        @{ Name = '手机 out'; Path = (Join-Path $LogDir 'mobile.out.log') },
        @{ Name = '手机 err'; Path = (Join-Path $LogDir 'mobile.err.log') },
        @{ Name = '数据库';   Path = $PgLog }
    )
    $any = $false
    foreach ($s in $sources) {
        Write-Host ('  -- ' + $s.Name + ' ({0}) --' -f $s.Path) -ForegroundColor DarkGray
        $errs = Get-FilteredLog $s.Path
        if ($errs -and $errs.Count -gt 0) {
            $any = $true
            $errs | ForEach-Object { Write-Host ('    ' + $_) -ForegroundColor Red }
        } else {
            Write-Host '    （无错误行）' -ForegroundColor DarkGray
        }
    }
    Write-Host '  -- Windows 应用程序事件日志（按本项目关键字过滤） --' -ForegroundColor DarkGray
    try {
        $kw = 'Word Planet|node|python|uvicorn|postgres|vite'
        $ev = Get-WinEvent -FilterHashtable @{ LogName = 'Application'; Level = 2, 3; StartTime = (Get-Date).AddHours(-24) } -MaxEvents 300 -ErrorAction Stop |
            Where-Object { $_.Message -match $kw } | Select-Object -First 20
        if ($ev) {
            $any = $true
            $ev | ForEach-Object {
                Write-Host ('    [{0}] {1}: {2}' -f $_.TimeCreated, $_.ProviderName, (($_.Message -split "`n")[0])) -ForegroundColor Red
            }
        } else {
            Write-Host '    （无匹配事件）' -ForegroundColor DarkGray
        }
    } catch {
        Write-Host ('    （系统事件日志读取失败：' + $_.Exception.Message + '）') -ForegroundColor DarkGray
    }
    if (-not $any) { Write-Host '  未发现错误。' -ForegroundColor Green }
}

function Show-Doctor {
    Write-Host ''
    Write-Host '  === 环境检查 ===' -ForegroundColor Cyan
    foreach ($p in 5432, 8000, 5273, 5274) {
        if (Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue) {
            Write-Host ("  端口 $p : 运行 / 占用")
        } else {
            Write-Host ("  端口 $p : 空闲")
        }
    }
    $py = Join-Path $Root 'backend\.venv\Scripts\python.exe'
    if (Test-Path $py) { Write-Host '  backend venv : OK' } else { Write-Host ('  backend venv : 缺失 ' + $py) -ForegroundColor Red }
    if (Test-Path (Join-Path $Root 'frontend\node_modules')) { Write-Host '  node_modules : OK' } else { Write-Host '  node_modules : 缺失' -ForegroundColor Red }
    if (Test-Path 'D:\PostgreSQL\bin\pg_ctl.exe') { Write-Host '  PostgreSQL   : OK' } else { Write-Host '  PostgreSQL   : 缺失 D:\PostgreSQL' -ForegroundColor Red }
    foreach ($c in 'node', 'npm', 'powershell') {
        if (Get-Command $c -ErrorAction SilentlyContinue) { Write-Host ("  $c : OK") } else { Write-Host ("  $c : 未找到") -ForegroundColor Yellow }
    }
    if (Get-Command node -ErrorAction SilentlyContinue) {
        Write-Host ('  node 版本 : ' + (& node -v 2>$null))
    }
}

if ($MenuAction -ne 'menu') {
    switch ($MenuAction) {
        'status' { & $Dev 'status' }
        'errors' { Show-Errors }
        'doctor' { Show-Doctor }
        'open'   { Invoke-OpenWeb }
    }
    exit
}

while ($true) {
    Show-Banner
    $choice = Read-Host '  请输入选项'
    switch ($choice) {
        '1' { & $Dev 'start' }
        '2' { & $Dev 'stop' }
        '3' { & $Dev 'restart' }
        '4' { & $Dev 'status' }
        '5' { Invoke-OpenWeb }
        '6' { Show-Errors }
        '7' { Show-Doctor }
        '0' { break }
        default { Write-Host '  无效选项，请重新选择' -ForegroundColor Yellow }
    }
    if ($choice -eq '0') { break }
    Pause-Menu
}
Write-Host '  已退出。' -ForegroundColor DarkGray
