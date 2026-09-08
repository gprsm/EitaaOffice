@echo off
setlocal
cd /d "%~dp0"
set "PYTHON="
set "PYTHON_ARGS="
if exist "python\python.exe" (
    set "PYTHON=python\python.exe"
    set "PYTHONPATH=%CD%\python-packages"
) else if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    where py >nul 2>nul || goto :missing
    set "PYTHON=py"
    set "PYTHON_ARGS=-3.13"
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
"%PYTHON%" %PYTHON_ARGS% -m eitaa_bridge.interfaces.cli --config bridge.json %SITE_ARG% doctor %*
set EXIT_CODE=%ERRORLEVEL%
pause
exit /b %EXIT_CODE%

:missing
echo Python runtime was not found. Reinstall or repair Eitaa Bridge.
pause
exit /b 1
