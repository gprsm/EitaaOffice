@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run setup_venv.bat first.
    pause
    exit /b 1
)
if "%~3"=="" (
    echo Usage: run_publication_status.bat SITE_KEY_OR_default "PEER_FILE" MESSAGE_ID
    pause
    exit /b 2
)
set "SITE_ARG="
if /I not "%~1"=="default" set "SITE_ARG=--site-key %~1"
".venv\Scripts\python.exe" -m eitaa_bridge.interfaces.cli --config bridge.json %SITE_ARG% publication status --peer-file "%~2" --message-id %~3
set EXIT_CODE=%ERRORLEVEL%
pause
exit /b %EXIT_CODE%
