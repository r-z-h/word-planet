#requires -Version 5.1
<#
  Word Planet - dev environment start/stop script

  Usage (from project root):
    .\dev.ps1 start      start PostgreSQL + backend + frontend
    .\dev.ps1 stop       stop everything
    .\dev.ps1 restart    restart everything
    .\dev.ps1 status     show current status

  If PowerShell blocks the script ("not digitally signed"), run:
    powershell -ExecutionPolicy Bypass -File .\dev.ps1 start

  ASCII-only on purpose: avoids codepage issues on Windows PowerShell 5.1.
#>

param(
    [Parameter(Position = 0)]
    [ValidateSet('start', 'stop', 'restart', 'status')]
    [string]$Action = 'status'
)

$ErrorActionPreference = 'Continue'

# ---------------- paths ----------------
$Root        = Split-Path -Parent $MyInvocation.MyCommand.Path
$PgHome      = 'D:\PostgreSQL'
$PgData      = Join-Path $PgHome 'data'
$PgLog       = Join-Path $PgHome 'log\server.log'
$BackendDir  = Join-Path $Root 'backend'
$FrontendDir = Join-Path $Root 'frontend'
$LogDir      = Join-Path $Root '.logs'

$BackendPort  = 8000
$FrontendPort = 5173   # HTTP  - desktop
$MobilePort   = 5174   # HTTPS - phone

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# ---------------- helpers ----------------
function Write-Step($msg)  { Write-Host "  $msg" }
function Write-Ok($msg)    { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn2($msg) { Write-Host "  [!]  $msg" -ForegroundColor Yellow }
function Write-Err2($msg)  { Write-Host "  [X]  $msg" -ForegroundColor Red }

function Test-Port($port) {
    $conn = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    return [bool]$conn
}

function Get-PortPid($port) {
    $conn = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue |
            Select-Object -First 1
    if ($conn) { return $conn.OwningProcess }
    return $null
}

function Wait-Port($port, $seconds = 40) {
    for ($i = 0; $i -lt $seconds; $i++) {
        if (Test-Port $port) { return $true }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Wait-PortClosed($port, $seconds = 20) {
    for ($i = 0; $i -lt $seconds; $i++) {
        if (-not (Test-Port $port)) { return $true }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Stop-PortProcess($port) {
    $procId = Get-PortPid $port
    if (-not $procId) { return }
    # /T kills the child tree, otherwise npm exits but vite keeps running
    & taskkill.exe /PID $procId /T /F 2>&1 | Out-Null
}

# Who is listening on this port, and is it one of ours?
# Never kill a port owner blindly: the user may have another project on it.
function Get-PortOwner($port) {
    $procId = Get-PortPid $port
    if (-not $procId) { return $null }
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$procId" -ErrorAction SilentlyContinue
    $cmd = ''
    if ($proc -and $proc.CommandLine) { $cmd = [string]$proc.CommandLine }
    return [pscustomobject]@{
        Pid         = $procId
        CommandLine = $cmd
        Ours        = ($cmd -like '*Word Planet*')
    }
}

# ---------------- PostgreSQL ----------------
function Start-Postgres {
    if (Test-Port 5432) { Write-Ok 'PostgreSQL already running (5432)'; return }

    if (-not (Test-Path $PgData)) {
        Write-Err2 "PostgreSQL data directory not found: $PgData"
        return
    }

    # a hard-killed server leaves postmaster.pid behind and pg_ctl refuses to start
    $stalePid = Join-Path $PgData 'postmaster.pid'
    if (Test-Path $stalePid) {
        Write-Warn2 'stale postmaster.pid found, removing'
        Remove-Item $stalePid -Force -ErrorAction SilentlyContinue
    }

    Write-Step 'starting PostgreSQL ...'
    # Use Start-Process with file redirection, never a pipeline. postgres
    # inherits the parent's stdout handle, so piping would keep the pipeline
    # open forever and hang this script.
    Start-Process -FilePath (Join-Path $PgHome 'bin\pg_ctl.exe') `
        -ArgumentList '-D', $PgData, '-l', $PgLog, 'start' `
        -RedirectStandardOutput (Join-Path $LogDir 'pg_start.out.log') `
        -RedirectStandardError  (Join-Path $LogDir 'pg_start.err.log') `
        -WindowStyle Hidden | Out-Null

    if (Wait-Port 5432 30) { Write-Ok 'PostgreSQL started (5432)' }
    else { Write-Err2 'PostgreSQL failed to start, see .logs\pg_start.err.log and D:\PostgreSQL\log\server.log' }
}

function Stop-Postgres {
    if (-not (Test-Port 5432)) { Write-Ok 'PostgreSQL already stopped'; return }
    Write-Step 'stopping PostgreSQL ...'
    Start-Process -FilePath (Join-Path $PgHome 'bin\pg_ctl.exe') `
        -ArgumentList '-D', $PgData, '-m', 'fast', 'stop' `
        -RedirectStandardOutput (Join-Path $LogDir 'pg_stop.out.log') `
        -RedirectStandardError  (Join-Path $LogDir 'pg_stop.err.log') `
        -WindowStyle Hidden | Out-Null
    if (Wait-PortClosed 5432 25) { Write-Ok 'PostgreSQL stopped' }
    else { Write-Warn2 'PostgreSQL still listening on 5432' }
}

# ---------------- backend ----------------
function Start-Backend {
    if (Test-Port $BackendPort) { Write-Ok "backend already running ($BackendPort)"; return }

    $python = Join-Path $BackendDir '.venv\Scripts\python.exe'
    if (-not (Test-Path $python)) { Write-Err2 "venv not found: $python"; return }

    Write-Step 'starting backend ...'
    Start-Process -FilePath $python `
        -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', "$BackendPort" `
        -WorkingDirectory $BackendDir `
        -RedirectStandardOutput (Join-Path $LogDir 'backend.out.log') `
        -RedirectStandardError  (Join-Path $LogDir 'backend.err.log') `
        -WindowStyle Hidden | Out-Null

    if (Wait-Port $BackendPort 40) { Write-Ok "backend started (http://localhost:$BackendPort)" }
    else { Write-Err2 'backend failed, see .logs\backend.err.log' }
}

function Stop-Backend {
    if (-not (Test-Port $BackendPort)) { Write-Ok 'backend already stopped'; return }
    Write-Step 'stopping backend ...'
    Stop-PortProcess $BackendPort
    if (Wait-PortClosed $BackendPort 20) { Write-Ok 'backend stopped' }
    else { Write-Warn2 'backend still listening' }
}

# ---------------- frontend ----------------
function Start-Frontend {
    if (-not (Test-Path (Join-Path $FrontendDir 'node_modules'))) {
        Write-Err2 'frontend/node_modules missing, run: cd frontend; npm install'
        return
    }

    $owner = Get-PortOwner $FrontendPort
    if ($owner -and $owner.Ours) {
        Write-Ok "frontend(desktop) already running ($FrontendPort)"
    } elseif ($owner) {
        Write-Err2 "port $FrontendPort is taken by ANOTHER program (pid $($owner.Pid)): $($owner.CommandLine)"
    } else {
        Write-Step 'starting frontend (http 5173) ...'
        Start-Process -FilePath 'cmd.exe' `
            -ArgumentList '/c', 'npm run dev' `
            -WorkingDirectory $FrontendDir `
            -RedirectStandardOutput (Join-Path $LogDir 'frontend.out.log') `
            -RedirectStandardError  (Join-Path $LogDir 'frontend.err.log') `
            -WindowStyle Hidden | Out-Null
        if (Wait-Port $FrontendPort 60) { Write-Ok "frontend(desktop) started (http://localhost:$FrontendPort)" }
        else { Write-Err2 'frontend(desktop) failed, see .logs\frontend.err.log' }
    }

    $mobileOwner = Get-PortOwner $MobilePort
    if ($mobileOwner -and $mobileOwner.Ours) {
        Write-Ok "frontend(mobile) already running ($MobilePort)"
    } elseif ($mobileOwner) {
        Write-Err2 "port $MobilePort is taken by ANOTHER program (pid $($mobileOwner.Pid)): $($mobileOwner.CommandLine)"
    } else {
        Write-Step 'starting frontend (https 5174) ...'
        Start-Process -FilePath 'cmd.exe' `
            -ArgumentList '/c', "set WP_HTTPS=1&& set WP_PORT=$MobilePort&& npm run dev" `
            -WorkingDirectory $FrontendDir `
            -RedirectStandardOutput (Join-Path $LogDir 'mobile.out.log') `
            -RedirectStandardError  (Join-Path $LogDir 'mobile.err.log') `
            -WindowStyle Hidden | Out-Null
        if (Wait-Port $MobilePort 60) { Write-Ok "frontend(mobile) started (https://<LAN-IP>:$MobilePort)" }
        else { Write-Err2 'frontend(mobile) failed, see .logs\mobile.err.log' }
    }
}

function Stop-Frontend {
    foreach ($port in @($FrontendPort, $MobilePort)) {
        $owner = Get-PortOwner $port
        if (-not $owner) { Write-Ok "frontend already stopped ($port)"; continue }
        if (-not $owner.Ours) {
            Write-Warn2 "port $port belongs to another program (pid $($owner.Pid)), skipped - NOT killed"
            continue
        }
        Write-Step "stopping frontend on $port ..."
        Stop-PortProcess $port
        if (Wait-PortClosed $port 20) { Write-Ok "frontend stopped ($port)" }
        else { Write-Warn2 "$port still listening" }
    }
}

# ---------------- status ----------------
function Show-Status {
    Write-Host ''
    Write-Host '  Word Planet status' -ForegroundColor Cyan
    Write-Host '  ----------------------------------------'

    $rows = @(
        @{ Name = 'PostgreSQL';        Port = 5432;         Extra = '5432';                       Managed = 'pg' },
        @{ Name = 'backend (FastAPI)'; Port = $BackendPort; Extra = "http://localhost:$BackendPort"; Managed = 'pg' },
        @{ Name = 'frontend desktop';  Port = $FrontendPort; Extra = "http://localhost:$FrontendPort"; Managed = 'app' },
        @{ Name = 'frontend mobile';   Port = $MobilePort;   Extra = "https://<LAN-IP>:$MobilePort";  Managed = 'app' }
    )

    foreach ($r in $rows) {
        $owner = Get-PortOwner $r.Port
        if ($owner -and ($r.Managed -eq 'pg' -or $owner.Ours)) {
            Write-Host ("  {0,-20} {1,-8} {2}" -f $r.Name, 'RUNNING', $r.Extra) -ForegroundColor Green
        } elseif ($owner) {
            Write-Host ("  {0,-20} {1,-8} {2}" -f $r.Name, 'FOREIGN', "pid $($owner.Pid) occupied by another program") -ForegroundColor Yellow
        } else {
            Write-Host ("  {0,-20} {1,-8} {2}" -f $r.Name, 'STOPPED', '') -ForegroundColor DarkGray
        }
    }

    if (Test-Port $BackendPort) {
        try {
            $h = Invoke-WebRequest "http://127.0.0.1:$BackendPort/api/health" -TimeoutSec 5 -UseBasicParsing
            Write-Host "  health: $($h.Content)" -ForegroundColor DarkGray
        } catch {
            Write-Warn2 'backend port is open but /api/health did not respond'
        }
    }

    $ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
           Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
           ForEach-Object { $_.IPAddress }
    if ($ips) { Write-Host "  LAN IPv4: $($ips -join ', ')" -ForegroundColor DarkGray }
    Write-Host ''
}

# ---------------- main ----------------
function Do-Start {
    Write-Host ''
    Write-Host '  === start ===' -ForegroundColor Cyan
    Start-Postgres
    Start-Backend
    Start-Frontend
    Show-Status
}

function Do-Stop {
    Write-Host ''
    Write-Host '  === stop ===' -ForegroundColor Cyan
    Stop-Frontend
    Stop-Backend
    Stop-Postgres
    Write-Host ''
}

switch ($Action) {
    'start'   { Do-Start }
    'stop'    { Do-Stop }
    'restart' { Do-Stop; Start-Sleep -Seconds 2; Do-Start }
    'status'  { Show-Status }
}
