@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run setup_venv.bat first.
    pause
    exit /b 1
)

set "SITE_ARG="
if "%~1"=="" goto :run
if /I "%~1"=="--online" goto :run
if /I "%~1"=="--skip-core-open" goto :run
if /I "%~1"=="default" (
    shift
    goto :run
)
set "SITE_ARG=--site-key %~1"
shift

:run
".venv\Scripts\python.exe" -m eitaa_bridge.interfaces.cli --config bridge.json %SITE_ARG% doctor %*
set EXIT_CODE=%ERRORLEVEL%
pause
exit /b %EXIT_CODE%
