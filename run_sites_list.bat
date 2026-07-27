@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run setup_venv.bat first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m eitaa_bridge.interfaces.cli --config bridge.json sites list
set EXIT_CODE=%ERRORLEVEL%
pause
exit /b %EXIT_CODE%
