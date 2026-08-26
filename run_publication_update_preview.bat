@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run setup_venv.bat first.
    pause
    exit /b 1
)
if "%~3"=="" (
    echo Usage: run_publication_update_preview.bat SITE_KEY_OR_default "PEER_FILE" MESSAGE_ID [TITLE] [CATEGORY_ID] [ALLOW_LIVE_yes_or_no] [RESTORE_TRASHED_yes_or_no]
    pause
    exit /b 2
)
set "SITE_ARG="
if /I not "%~1"=="default" set "SITE_ARG=--site-key %~1"
set "TITLE_ARG="
if not "%~4"=="" set TITLE_ARG=--title "%~4"
set "CATEGORY_ARG="
if not "%~5"=="" set "CATEGORY_ARG=--category-id %~5"
set "LIVE_ARG="
if /I "%~6"=="yes" set "LIVE_ARG=--allow-live-update"
if /I "%~6"=="true" set "LIVE_ARG=--allow-live-update"
if "%~6"=="1" set "LIVE_ARG=--allow-live-update"
set "RESTORE_ARG="
if /I "%~7"=="yes" set "RESTORE_ARG=--restore-trashed"
if /I "%~7"=="true" set "RESTORE_ARG=--restore-trashed"
if "%~7"=="1" set "RESTORE_ARG=--restore-trashed"
".venv\Scripts\python.exe" -m eitaa_bridge.interfaces.cli --config bridge.json %SITE_ARG% publication update-preview --peer-file "%~2" --message-id %~3 %TITLE_ARG% %CATEGORY_ARG% %LIVE_ARG% %RESTORE_ARG%
set EXIT_CODE=%ERRORLEVEL%
pause
exit /b %EXIT_CODE%
