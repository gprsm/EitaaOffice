@echo off
setlocal
cd /d "%~dp0"
where msedge >nul 2>nul
if %ERRORLEVEL% equ 0 (
    start msedge.exe --app=http://127.0.0.1:8765/
) else (
    start http://127.0.0.1:8765/
)
exit /b 0
