@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
if "%~1"=="" (
    echo Usage: upgrade_from_ui_mvp6_0.bat "PATH_TO_OLD_eitaa_bridge_v0_7_ui_mvp6_0"
    echo Extract MVP 6.1 to a new folder, then pass the old MVP 6.0 folder here.
    pause
    exit /b 2
)
set "SOURCE=%~f1"
if /I "%SOURCE%"=="%CD%" (
    echo Source and destination folders must be different.
    pause
    exit /b 2
)
if not exist "%SOURCE%\bridge.json" (
    echo Source bridge.json was not found.
    pause
    exit /b 1
)

rem Protect the new destination before changing it.
if exist "bridge.json" (
  set "PYTHON=.venv\Scripts\python.exe"
  if not exist "!PYTHON!" set "PYTHON=py"
  "!PYTHON!" scripts\backup_runtime.py --quiet
  if errorlevel 1 (
    echo Mandatory destination backup failed. Migration stopped.
    pause
    exit /b 1
  )
)

rem Protect the complete old runtime before copying any user data.
if exist "%SOURCE%\.venv\Scripts\python.exe" if exist "%SOURCE%\scripts\backup_runtime.py" (
  pushd "%SOURCE%"
  ".venv\Scripts\python.exe" scripts\backup_runtime.py --quiet
  if errorlevel 1 (
    popd
    echo Mandatory source backup failed. Migration stopped.
    pause
    exit /b 1
  )
  popd
) else (
  if not exist "backups\migration" mkdir "backups\migration"
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$stamp=Get-Date -Format yyyyMMdd-HHmmss; $items=@('%SOURCE%\bridge.json','%SOURCE%\.env','%SOURCE%\.eitaa_session.json','%SOURCE%\composition.json','%SOURCE%\data','%SOURCE%\ui\preferences.json') ^| Where-Object { Test-Path $_ }; if(-not $items){exit 1}; Compress-Archive -Force -Path $items -DestinationPath ('backups\migration\mvp6_0-source-'+$stamp+'.zip')" >nul 2>nul
  if errorlevel 1 (
    echo Source fallback backup failed. Migration stopped.
    pause
    exit /b 1
  )
)

copy /Y "%SOURCE%\bridge.json" "bridge.json" >nul
if exist "%SOURCE%\.env" copy /Y "%SOURCE%\.env" ".env" >nul
if exist "%SOURCE%\composition.json" copy /Y "%SOURCE%\composition.json" "composition.json" >nul
for %%F in ("%SOURCE%\selected*.json") do if exist "%%~fF" copy /Y "%%~fF" "." >nul
if exist "%SOURCE%\.eitaa_session.json" copy /Y "%SOURCE%\.eitaa_session.json" ".eitaa_session.json" >nul

if exist "%SOURCE%\data" (
  robocopy "%SOURCE%\data" "data" /E /COPY:DAT /DCOPY:DAT /R:2 /W:1 /XJ /NFL /NDL /NP >nul
  if errorlevel 8 (
    echo Copying the source data folder failed. Migration stopped.
    pause
    exit /b 1
  )
)

if exist "%SOURCE%\ui\preferences.json" (
    if not exist "ui" mkdir "ui"
    copy /Y "%SOURCE%\ui\preferences.json" "ui\preferences.json" >nul
)
if not exist "ui\fonts" mkdir "ui\fonts"
for %%F in ("%SOURCE%\ui\fonts\*.woff2") do if exist "%%~fF" copy /Y "%%~fF" "ui\fonts" >nul

if exist "data\eitaa_messages.sqlite3" copy /Y "data\eitaa_messages.sqlite3" "data\eitaa_messages.before_mvp6_1.backup.sqlite3" >nul

rem Old diagnostics and runtime logs intentionally remain in the old folder and its backup.
rem Copying tens of thousands of historical log files would slow the office computer.
echo.
echo Migration completed safely.
echo Session, database, messages, media cache, settings, compositions, and UI metadata were copied.
echo Historical diagnostics, old .venv, node_modules, wheels, and old UI builds were not copied.
echo Run install_app.bat, run_doctor.bat, and EitaaBridge.bat next.
pause
exit /b 0
