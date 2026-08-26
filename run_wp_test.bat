@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run setup_venv.bat first.
    pause
    exit /b 1
)

set "SITE_ARG="
if not "%~1"=="" if /I not "%~1"=="default" set "SITE_ARG=--site-key %~1"

".venv\Scripts\python.exe" -m eitaa_bridge.interfaces.cli --config bridge.json %SITE_ARG% wp test
set EXIT_CODE=%ERRORLEVEL%
pause
exit /b %EXIT_CODE%
