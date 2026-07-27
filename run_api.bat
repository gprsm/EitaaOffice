@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run setup_venv.bat first.
    pause
    exit /b 1
)
set "HOST=127.0.0.1"
set "PORT=8765"
if not "%~1"=="" set "HOST=%~1"
if not "%~2"=="" set "PORT=%~2"
echo Starting Eitaa Bridge local API...
".venv\Scripts\python.exe" -m eitaa_bridge.interfaces.http_api --config bridge.json --host "%HOST%" --port %PORT%
exit /b %ERRORLEVEL%
