@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
    echo Usage: upgrade_from_ui_mvp1.bat "PATH_TO_eitaa_bridge_v0_7_ui_mvp1"
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
echo Configuration, session, local database, media, composition state, and peer files were copied.
echo node_modules and the old package-lock.json were intentionally not copied.
echo install_app.bat installs the bundled Core 7.4.4 Wheel.
echo Run install_app.bat next.
pause
exit /b 0
