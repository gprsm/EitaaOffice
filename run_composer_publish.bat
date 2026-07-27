@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run setup_venv.bat first.
    pause
    exit /b 1
)
if "%~1"=="" (
    echo Usage: run_composer_publish.bat "COMPOSITION_JSON" [MAX_MEDIA_MB]
    pause
    exit /b 2
)
set "MAX_MB=100"
if not "%~2"=="" set "MAX_MB=%~2"
".venv\Scripts\python.exe" -m eitaa_bridge.interfaces.cli --config bridge.json composer publish --file "%~1" --max-media-mb %MAX_MB%
set EXIT_CODE=%ERRORLEVEL%
pause
exit /b %EXIT_CODE%
