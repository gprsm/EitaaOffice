@echo off
setlocal
cd /d "%~dp0"
set "BACKUP=%~1"
if "%BACKUP%"=="" (
  for /f "usebackq delims=" %%F in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "Add-Type -AssemblyName System.Windows.Forms; $d=New-Object System.Windows.Forms.OpenFileDialog; $d.Filter='Eitaa Bridge backup (*.zip)|*.zip'; if($d.ShowDialog() -eq 'OK'){Write-Output $d.FileName}"`) do set "BACKUP=%%F"
)
if "%BACKUP%"=="" exit /b 2
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
"%PYTHON%" %PYTHON_ARGS% scripts\restore_runtime.py "%BACKUP%" --yes
if errorlevel 1 (
  echo Restore failed. No unverified backup was applied.
  pause
  exit /b 1
)
echo Restore completed. Restart Eitaa Bridge.
pause
exit /b 0

:missing
echo Python runtime was not found.
pause
exit /b 1
