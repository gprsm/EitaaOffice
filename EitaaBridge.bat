@echo off
setlocal
cd /d "%~dp0"
if exist "EitaaBridge-win32-x64\EitaaBridge.exe" (
  start "" "EitaaBridge-win32-x64\EitaaBridge.exe"
  exit /b 0
)
if exist "EitaaBridge.exe" (
  start "" "EitaaBridge.exe"
  exit /b 0
)
if not exist ".venv\Scripts\pythonw.exe" (
  echo Backend environment is missing. Run install_app.bat first.
  pause
  exit /b 1
)
if not exist "ui\dist\index.html" (
  echo Production UI build is missing. Re-extract the complete package.
  pause
  exit /b 1
)
start "" wscript.exe "%~dp0EitaaBridgeOffice.vbs"
exit /b 0
