@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run setup_venv.bat first.
    pause
    exit /b 1
)
set "HOST=127.0.0.1"
set "PORT=8791"
if not "%~1"=="" set "HOST=%~1"
if not "%~2"=="" set "PORT=%~2"
echo Starting Bale branch local API (loopback only)...
".venv\Scripts\python.exe" -m eitaa_bridge.application.bale_client.api_server --host "%HOST%" --port %PORT%
exit /b %ERRORLEVEL%
