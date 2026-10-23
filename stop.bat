@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo.
echo  Stopping Word Planet ...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev.ps1" stop

echo.
pause
