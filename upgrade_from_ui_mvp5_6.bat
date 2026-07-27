@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
if "%~1"=="" (
    echo Usage: upgrade_from_ui_mvp5_6.bat "PATH_TO_eitaa_bridge_v0_7_ui_mvp5_6"
    pause
    exit /b 2
)
set "SOURCE=%~f1"
if not exist "%SOURCE%\bridge.json" (
    echo Source bridge.json was not found.
    pause
    exit /b 1
)

rem Always protect the destination before changing it.
if exist "bridge.json" (
  set "PYTHON=.venv\Scripts\python.exe"
  if not exist "!PYTHON!" set "PYTHON=py"
  "!PYTHON!" scripts\backup_runtime.py --quiet
  if errorlevel 1 (
    echo Mandatory destination backup failed. Upgrade stopped.
    pause
    exit /b 1
  )
)

rem Create a complete source-state backup using the source package when possible.
if exist "%SOURCE%\.venv\Scripts\python.exe" if exist "%SOURCE%\scripts\backup_runtime.py" (
  pushd "%SOURCE%"
  ".venv\Scripts\python.exe" scripts\backup_runtime.py --quiet
  if errorlevel 1 (
    popd
    echo Mandatory source backup failed. Upgrade stopped.
    pause
    exit /b 1
  )
  popd
) else (
  if not exist "backups\migration" mkdir "backups\migration"
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$stamp=Get-Date -Format yyyyMMdd-HHmmss; $items=@('%SOURCE%\bridge.json','%SOURCE%\.env','%SOURCE%\.eitaa_session.json','%SOURCE%\data','%SOURCE%\ui\fonts','%SOURCE%\ui\preferences.json') ^| Where-Object { Test-Path $_ }; if(-not $items){exit 1}; Compress-Archive -Force -Path $items -DestinationPath ('backups\migration\mvp5_6-source-'+$stamp+'.zip')" >nul 2>nul
  if errorlevel 1 (
    echo Source fallback backup failed. Upgrade stopped.
    pause
    exit /b 1
  )
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
for %%F in ("%SOURCE%\ui\fonts\*.woff2") do if exist "%%~fF" copy /Y "%%~fF" "ui\fonts" >nul
if exist "data\eitaa_messages.sqlite3" copy /Y "data\eitaa_messages.sqlite3" "data\eitaa_messages.before_mvp6.backup.sqlite3" >nul

echo Configuration, Session, database, media, compositions, UI metadata, and fonts were copied.
echo Source and destination backups were created before migration.
echo Old .venv, node_modules, wheels, and UI build files were intentionally not copied.
echo Run install_app.bat, run_doctor.bat, and EitaaBridge.bat next.
pause
exit /b 0
