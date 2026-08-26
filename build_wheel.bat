@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run setup_venv.bat first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" scripts\build_wheel_stdlib.py --root . --output-dir dist --force
set EXIT_CODE=%ERRORLEVEL%
pause
exit /b %EXIT_CODE%
