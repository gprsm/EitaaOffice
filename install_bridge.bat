@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run setup_venv.bat first.
    pause
    exit /b 1
)
if not exist "dist\eitaa_bridge-0.4.0.dev3-py3-none-any.whl" (
    echo Build artifact was not found. Run build_wheel.bat first.
    pause
    exit /b 2
)
".venv\Scripts\python.exe" -m pip install --find-links vendor --upgrade "dist\eitaa_bridge-0.4.0.dev3-py3-none-any.whl"
if errorlevel 1 exit /b %errorlevel%
echo Bridge wheel installed.
pause
