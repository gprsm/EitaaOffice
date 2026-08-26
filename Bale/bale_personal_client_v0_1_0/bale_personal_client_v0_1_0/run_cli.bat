@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\bale-client.exe (
  echo Run setup_windows.bat first.
  exit /b 1
)
.venv\Scripts\bale-client.exe %*
