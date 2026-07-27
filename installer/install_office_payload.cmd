@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "TARGET=%LOCALAPPDATA%\Programs\EitaaBridge"
set "TEMPSTAGE=%TEMP%\EitaaBridgeInstall-%RANDOM%-%RANDOM%"
set "PAYLOAD=%~dp0office_payload.zip"

if not exist "%PAYLOAD%" (
  echo office_payload.zip was not found.
  pause
  exit /b 1
)
mkdir "%TEMPSTAGE%" >nul 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%PAYLOAD%' -DestinationPath '%TEMPSTAGE%' -Force"
if errorlevel 1 goto :failed
if not exist "%TEMPSTAGE%\app\VERSION.txt" goto :failed

if exist "%TARGET%\python\python.exe" if exist "%TEMPSTAGE%\app\scripts\office_runtime.py" (
  set "PYTHONPATH=%TARGET%\python-packages"
  "%TARGET%\python\python.exe" "%TEMPSTAGE%\app\scripts\office_runtime.py" prepare-install --root "%TARGET%" --quiet --allow-legacy-owned
  set "PYTHONPATH="
  if errorlevel 1 goto :failed
)

if exist "%TARGET%\python\python.exe" if exist "%TARGET%\scripts\backup_runtime.py" (
  "%TARGET%\python\python.exe" "%TARGET%\scripts\backup_runtime.py" --quiet >nul 2>nul
)

mkdir "%TARGET%" >nul 2>nul

rem Managed code directories must mirror the clean payload. A plain /E copy
rem leaves old dist-info and removed modules behind (for example dev15 beside
rem dev17), causing importlib.metadata to report the previous package version.
for %%D in (python python-packages dist vendor scripts docs ui) do (
  if exist "%TEMPSTAGE%\app\%%D" (
    robocopy "%TEMPSTAGE%\app\%%D" "%TARGET%\%%D" /MIR /R:2 /W:1 /NFL /NDL /NP /XJ >nul
    if errorlevel 8 goto :failed
  )
)

rem Copy root payload files while preserving private/runtime directories and
rem excluding the managed directories already mirrored above.
robocopy "%TEMPSTAGE%\app" "%TARGET%" /E /R:2 /W:1 /NFL /NDL /NP /XJ /XD python python-packages dist vendor scripts docs ui runtime backups data diagnostics /XF bridge.json .env .eitaa_session.json composition.json transfer-backup.zip >nul
if errorlevel 8 goto :failed

if not exist "%TARGET%\bridge.json" copy /Y "%TARGET%\bridge.example.json" "%TARGET%\bridge.json" >nul
if not exist "%TARGET%\.env" copy /Y "%TARGET%\.env.example" "%TARGET%\.env" >nul
if not exist "%TARGET%\runtime\logs" mkdir "%TARGET%\runtime\logs"
if not exist "%TARGET%\backups\runtime" mkdir "%TARGET%\backups\runtime"

set "PYTHONPATH=%TARGET%\python-packages"
"%TARGET%\python\python.exe" "%TARGET%\scripts\check_runtime_environment.py"
if errorlevel 1 goto :failed
"%TARGET%\python\python.exe" -c "import eitaa_core.infrastructure.diagnostics; import eitaa_bridge.infrastructure.diagnostics; print('Installed Office diagnostics packages: OK')"
if errorlevel 1 goto :failed
set "PYTHONPATH="

if exist "%TEMPSTAGE%\app\transfer-backup.zip" (
  "%TARGET%\python\python.exe" "%TARGET%\scripts\restore_runtime.py" "%TEMPSTAGE%\app\transfer-backup.zip" --yes --skip-current-backup
  if errorlevel 1 goto :failed
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$w=New-Object -ComObject WScript.Shell; $start=[Environment]::GetFolderPath('StartMenu')+'\Programs\Eitaa Bridge.lnk'; $desktop=[Environment]::GetFolderPath('Desktop')+'\Eitaa Bridge.lnk'; foreach($p in @($start,$desktop)){ $s=$w.CreateShortcut($p); $s.TargetPath=$env:WINDIR+'\System32\wscript.exe'; $s.Arguments='""%TARGET%\EitaaBridgeOffice.vbs""'; $s.WorkingDirectory='%TARGET%'; $s.Description='Eitaa Bridge Office'; $s.Save() }"

start "" wscript.exe "%TARGET%\EitaaBridgeOffice.vbs"
rmdir /S /Q "%TEMPSTAGE%" >nul 2>nul
echo.
echo Eitaa Bridge Office installed successfully.
echo Installation path: %TARGET%
pause
exit /b 0

:failed
echo.
echo Installation failed. Existing runtime data was not intentionally deleted.
echo Temporary staging path: %TEMPSTAGE%
pause
exit /b 1
