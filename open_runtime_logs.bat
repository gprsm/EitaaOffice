@echo off
setlocal
cd /d "%~dp0"
if not exist "runtime\logs" mkdir "runtime\logs"
start "" explorer.exe "%~dp0runtime\logs"
exit /b 0
