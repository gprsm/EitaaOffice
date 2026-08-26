@echo off
setlocal
cd /d "%~dp0"

set "SOURCE=%~1"
if "%SOURCE%"=="" (
    echo Usage: upgrade_from_wordpress_publication1.bat "FULL_PATH_TO_V0_3_FOLDER"
    echo This copies only bridge.json and .env. No source merge is performed.
    pause
    exit /b 2
)

if not exist "%SOURCE%" (
    echo WordPress Publication 1 folder was not found.
    pause
    exit /b 2
)

if exist "%SOURCE%\bridge.json" copy /Y "%SOURCE%\bridge.json" "bridge.json" >nul
if exist "%SOURCE%\.env" copy /Y "%SOURCE%\.env" ".env" >nul

call setup_venv.bat
exit /b %ERRORLEVEL%
