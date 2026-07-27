@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
    echo Usage: upgrade_from_ui_mvp5_3.bat "PATH_TO_eitaa_bridge_v0_7_ui_mvp5_3"
    pause
    exit /b 2
)
set "SOURCE=%~f1"
if not exist "%SOURCE%\bridge.json" (
    echo Source bridge.json was not found.
    pause
    exit /b 1
)
copy /Y "%SOURCE%\bridge.json" "bridge.json" >nul
if exist "%SOURCE%\.env" copy /Y "%SOURCE%\.env" ".env" >nul
if exist "%SOURCE%\composition.json" copy /Y "%SOURCE%\composition.json" "composition.json" >nul
for %%F in ("%SOURCE%\selected*.json") do if exist "%%~fF" copy /Y "%%~fF" "." >nul
if exist "%SOURCE%\data" xcopy /E /I /Y "%SOURCE%\data" "data" >nul
if exist "%SOURCE%\.eitaa_session.json" copy /Y "%SOURCE%\.eitaa_session.json" ".eitaa_session.json" >nul
if exist "%SOURCE%\diagnostics" xcopy /E /I /Y "%SOURCE%\diagnostics" "diagnostics" >nul
if exist "%SOURCE%\ui\preferences.json" (
    if not exist "ui" mkdir "ui"
    copy /Y "%SOURCE%\ui\preferences.json" "ui\preferences.json" >nul
)
if not exist "ui\fonts" mkdir "ui\fonts"
if exist "%SOURCE%\ui\fonts\IRANSansWeb-Regular.woff2" copy /Y "%SOURCE%\ui\fonts\IRANSansWeb-Regular.woff2" "ui\fonts\IRANSansWeb-Regular.woff2" >nul
if exist "%SOURCE%\ui\fonts\IRANSansWeb-Bold.woff2" copy /Y "%SOURCE%\ui\fonts\IRANSansWeb-Bold.woff2" "ui\fonts\IRANSansWeb-Bold.woff2" >nul
if exist "%SOURCE%\ui\fonts\IRANSansWeb.woff2" if not exist "ui\fonts\IRANSansWeb-Regular.woff2" copy /Y "%SOURCE%\ui\fonts\IRANSansWeb.woff2" "ui\fonts\IRANSansWeb-Regular.woff2" >nul
if exist "data\eitaa_messages.sqlite3" copy /Y "data\eitaa_messages.sqlite3" "data\eitaa_messages.before_schema8.backup.sqlite3" >nul
echo Configuration, session, database, UI metadata, media, and optional fonts were copied.
echo The copied SQLite database was backed up before the new application opens it.
echo Old .venv, node_modules, Core Wheel, and UI build files were intentionally not copied.
echo Run install_app.bat next. It installs Core 7.4.4 and Bridge UI MVP 5.6.
pause
exit /b 0
