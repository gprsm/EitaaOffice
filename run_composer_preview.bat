@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run setup_venv.bat first.
    pause
    exit /b 1
)
if "%~1"=="" (
    echo Usage: run_composer_preview.bat "COMPOSITION_JSON"
    pause
    exit /b 2
)
".venv\Scripts\python.exe" -m eitaa_bridge.interfaces.cli --config bridge.json composer preview --file "%~1"
set EXIT_CODE=%ERRORLEVEL%
pause
exit /b %EXIT_CODE%
