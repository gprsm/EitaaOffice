@echo off
setlocal
cd /d "%~dp0"
set "PYTHON=.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=py"
for /f "usebackq delims=" %%F in (`"%PYTHON%" scripts\create_diagnostics_bundle.py`) do set "BUNDLE=%%F"
if errorlevel 1 (
  echo Diagnostics creation failed.
  pause
  exit /b 1
)
echo Safe diagnostics bundle:
echo %BUNDLE%
explorer.exe /select,"%BUNDLE%"
pause
