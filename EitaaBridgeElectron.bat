@echo off
setlocal
cd /d "%~dp0"
if not exist "ui\node_modules\electron\dist\electron.exe" (
  echo Electron runtime is not installed. Run setup_ui.bat first.
  pause
  exit /b 1
)
if not exist "ui\dist\index.html" (
  echo Production UI build is missing. Run setup_ui.bat first.
  pause
  exit /b 1
)
cd /d "%~dp0ui"
start "" /b node_modules\electron\dist\electron.exe .
exit /b 0
