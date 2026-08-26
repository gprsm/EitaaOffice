@echo off
setlocal
cd /d "%~dp0"
set "PYTHON=.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=py"
"%PYTHON%" scripts\backup_runtime.py %*
if errorlevel 1 (
  echo Backup failed.
  pause
  exit /b 1
)
echo Backup completed.
pause
