@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo.
echo  Starting Word Planet (PostgreSQL + backend + frontend) ...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev.ps1" start

echo.
echo  ------------------------------------------------------------
echo  Desktop : http://localhost:5173
echo  Phone   : https://^<LAN-IP^>:5174
echo  ------------------------------------------------------------
echo.
pause
