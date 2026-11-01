# Download cloudflared.exe into tools/bin (the binary is NOT committed to git).
# Usage:  .\tools\get-cloudflared.ps1
$ErrorActionPreference = 'Stop'

$dir = Join-Path $PSScriptRoot 'bin'
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }

$exe = Join-Path $dir 'cloudflared.exe'
if (Test-Path $exe) {
    Write-Host "[ok] already exists: $exe"
    return
}

$url = 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe'
Write-Host "Downloading $url ..."
Invoke-WebRequest -Uri $url -OutFile $exe -UseBasicParsing
Write-Host "[ok] saved: $exe"
