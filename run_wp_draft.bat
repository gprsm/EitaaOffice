@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run setup_venv.bat first.
    pause
    exit /b 1
)
if "%~3"=="" (
    echo Usage: run_wp_draft.bat SITE_KEY_OR_default "POST_TITLE" "CONTENT_FILE" [CATEGORY_ID] [FEATURED_MEDIA_ID]
    pause
    exit /b 2
)

set "SITE_ARG="
if /I not "%~1"=="default" set "SITE_ARG=--site-key %~1"
set "CATEGORY_ARG="
if not "%~4"=="" set "CATEGORY_ARG=--category-id %~4"
set "MEDIA_ARG="
if not "%~5"=="" set "MEDIA_ARG=--featured-media-id %~5"

".venv\Scripts\python.exe" -m eitaa_bridge.interfaces.cli --config bridge.json %SITE_ARG% wp draft --title "%~2" --content-file "%~3" %CATEGORY_ARG% %MEDIA_ARG%
set EXIT_CODE=%ERRORLEVEL%
pause
exit /b %EXIT_CODE%
