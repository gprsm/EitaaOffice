@echo off
setlocal
cd /d "%~dp0ui"
if not exist "node_modules" (
    echo Run setup_ui.bat first.
    pause
    exit /b 1
)
call npm run check
if errorlevel 1 goto :failed
call npm run build
if errorlevel 1 goto :failed
echo UI TypeScript and production build checks passed.
pause
exit /b 0
:failed
echo UI checks failed.
pause
exit /b 1
