@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Python virtual environment not found in .venv.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" scripts\background_server.py start
exit /b %ERRORLEVEL%
