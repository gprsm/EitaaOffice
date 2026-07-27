@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run setup_venv.bat first.
    pause
    exit /b 1
)
if "%~3"=="" (
    echo Usage: run_publication_restore.bat SITE_KEY_OR_default "PEER_FILE" MESSAGE_ID [TITLE] [CATEGORY_ID] [MAX_MEDIA_MB]
    pause
    exit /b 2
)
set "SITE_ARG="
if /I not "%~1"=="default" set "SITE_ARG=--site-key %~1"
set "TITLE_ARG="
if not "%~4"=="" set TITLE_ARG=--title "%~4"
set "CATEGORY_ARG="
if not "%~5"=="" set "CATEGORY_ARG=--category-id %~5"
set "MAX_ARG="
if not "%~6"=="" set "MAX_ARG=--max-media-mb %~6"
".venv\Scripts\python.exe" -m eitaa_bridge.interfaces.cli --config bridge.json %SITE_ARG% publication update --peer-file "%~2" --message-id %~3 %TITLE_ARG% %CATEGORY_ARG% %MAX_ARG% --restore-trashed
set EXIT_CODE=%ERRORLEVEL%
pause
exit /b %EXIT_CODE%
