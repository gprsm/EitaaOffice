@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Backend environment is missing. Run install_app.bat first.
    pause
    exit /b 1
)
if not exist "ui\node_modules\electron\dist\electron.exe" (
    echo Desktop runtime is missing. Run install_app.bat first.
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
