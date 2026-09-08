@echo off
setlocal
cd /d "%~dp0"
set "PYTHON="
set "PYTHON_ARGS="
if exist "python\python.exe" (
  set "PYTHON=python\python.exe"
  set "PYTHONPATH=%CD%\python-packages"
) else if exist ".venv\Scripts\python.exe" (
  set "PYTHON=.venv\Scripts\python.exe"
) else (
  where py >nul 2>nul || goto :missing
  set "PYTHON=py"
  set "PYTHON_ARGS=-3.13"
)
for /f "usebackq delims=" %%F in (`"%PYTHON%" %PYTHON_ARGS% scripts\create_diagnostics_bundle.py`) do set "BUNDLE=%%F"
if errorlevel 1 (
  echo Diagnostics creation failed.
  pause
  exit /b 1
)
echo Safe diagnostics bundle:
echo %BUNDLE%
explorer.exe /select,"%BUNDLE%"
pause
exit /b 0

:missing
echo Python runtime was not found.
pause
exit /b 1
