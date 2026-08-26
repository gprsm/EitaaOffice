@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Backend environment is missing. Run setup_venv.bat first.
    exit /b 1
)
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"
if "%~1"=="" goto :usage
if /I "%~1"=="check" goto :run
if /I "%~1"=="start" goto :run
if /I "%~1"=="firewall-plan" goto :run
goto :usage

:run
".venv\Scripts\python.exe" -m eitaa_bridge.interfaces.windows_lan %1 --config bridge.json --ui-root ui\dist
exit /b %ERRORLEVEL%

:usage
echo Usage: EitaaBridgeLanServer.bat check ^| start ^| firewall-plan
echo This launcher never changes bridge.json or applies a Firewall rule.
exit /b 2
