@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run setup_venv.bat first.
    pause
    exit /b 1
)
if "%~2"=="" (
    echo Usage: run_wp_media_upload.bat SITE_KEY_OR_default "MEDIA_FILE" [ALT_TEXT] [MIME_TYPE]
    pause
    exit /b 2
)

set "SITE_ARG="
if /I not "%~1"=="default" set "SITE_ARG=--site-key %~1"
set "ALT_ARG="
if not "%~3"=="" set ALT_ARG=--alt-text "%~3"
set "MIME_ARG="
if not "%~4"=="" set "MIME_ARG=--mime-type %~4"

".venv\Scripts\python.exe" -m eitaa_bridge.interfaces.cli --config bridge.json %SITE_ARG% wp media upload --file "%~2" %ALT_ARG% %MIME_ARG%
set EXIT_CODE=%ERRORLEVEL%
pause
exit /b %EXIT_CODE%
