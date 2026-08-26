@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run setup_venv.bat first.
    pause
    exit /b 1
)
if "%~3"=="" (
    echo Usage: run_publication_update.bat SITE_KEY_OR_default "PEER_FILE" MESSAGE_ID [TITLE] [CATEGORY_ID] [MAX_MEDIA_MB] [ALLOW_LIVE_yes_or_no] [OVERWRITE_DRIFT_yes_or_no] [RESTORE_TRASHED_yes_or_no]
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
set "LIVE_ARG="
if /I "%~7"=="yes" set "LIVE_ARG=--allow-live-update"
if /I "%~7"=="true" set "LIVE_ARG=--allow-live-update"
if "%~7"=="1" set "LIVE_ARG=--allow-live-update"
set "DRIFT_ARG="
if /I "%~8"=="yes" set "DRIFT_ARG=--overwrite-remote-drift"
if /I "%~8"=="true" set "DRIFT_ARG=--overwrite-remote-drift"
if "%~8"=="1" set "DRIFT_ARG=--overwrite-remote-drift"
set "RESTORE_ARG="
if /I "%~9"=="yes" set "RESTORE_ARG=--restore-trashed"
if /I "%~9"=="true" set "RESTORE_ARG=--restore-trashed"
if "%~9"=="1" set "RESTORE_ARG=--restore-trashed"
".venv\Scripts\python.exe" -m eitaa_bridge.interfaces.cli --config bridge.json %SITE_ARG% publication update --peer-file "%~2" --message-id %~3 %TITLE_ARG% %CATEGORY_ARG% %MAX_ARG% %LIVE_ARG% %DRIFT_ARG% %RESTORE_ARG%
set EXIT_CODE=%ERRORLEVEL%
pause
exit /b %EXIT_CODE%
