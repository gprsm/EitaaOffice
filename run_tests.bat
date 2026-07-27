@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run setup_venv.bat first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m pytest
if errorlevel 1 goto :failed
if exist "ui\node_modules" (
    cd /d "%~dp0ui"
    call npm run check
    if errorlevel 1 goto :failed
    call npm run build
    if errorlevel 1 goto :failed
)
echo All available backend and UI checks passed.
pause
exit /b 0
:failed
echo Tests failed.
pause
exit /b 1
