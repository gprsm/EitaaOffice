@echo off
setlocal
cd /d "%~dp0"

set "SOURCE=%~1"
if "%SOURCE%"=="" (
    echo Usage: upgrade_from_foundation3.bat "FULL_PATH_TO_FOUNDATION3_FOLDER"
    echo This copies only bridge.json and .env, then prepares WordPress Update 1.
    pause
    exit /b 2
)

if not exist "%SOURCE%" (
    echo Foundation 3 folder was not found.
    pause
    exit /b 2
)

if exist "%SOURCE%\bridge.json" copy /Y "%SOURCE%\bridge.json" "bridge.json" >nul
if exist "%SOURCE%\.env" copy /Y "%SOURCE%\.env" ".env" >nul

call setup_venv.bat
exit /b %ERRORLEVEL%
