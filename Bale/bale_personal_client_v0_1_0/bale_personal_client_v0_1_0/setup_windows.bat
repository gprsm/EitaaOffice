@echo off
setlocal
cd /d "%~dp0"
if not exist .venv (
  py -3.14 -m venv .venv
  if errorlevel 1 python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -e . --no-build-isolation
if errorlevel 1 (
  echo Installation failed.
  exit /b 1
)
echo.
echo Installed successfully.
echo Run run_lab.bat or .venv\Scripts\bale-client.exe --help
