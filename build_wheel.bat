@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PIP_PROGRESS_BAR=off"
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run setup_venv.bat first.
    pause
    exit /b 1
)
if exist build rmdir /s /q build
if exist src\eitaa_bridge.egg-info rmdir /s /q src\eitaa_bridge.egg-info
".venv\Scripts\python.exe" -m pip wheel --no-deps . -w dist
set EXIT_CODE=%ERRORLEVEL%
pause
exit /b %EXIT_CODE%
