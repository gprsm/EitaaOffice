@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run setup_venv.bat first.
    pause
    exit /b 1
)
set "HOST=127.0.0.1"
set "PORT=8791"
if not "%~1"=="" set "HOST=%~1"
if not "%~2"=="" set "PORT=%~2"

rem Stable API token kept in data/bale_api.token (gitignored) so the UI
rem keeps working across restarts; generated once on first run.
set "TOKEN_FILE=data\bale_api.token"
set "TOKEN="
if exist "%TOKEN_FILE%" set /p TOKEN=<"%TOKEN_FILE%"
if "%TOKEN%"=="" (
    if not exist "data" mkdir "data"
    ".venv\Scripts\python.exe" -c "import secrets,pathlib;pathlib.Path(r'data/bale_api.token').write_text(secrets.token_urlsafe(24),encoding='utf-8')"
    set /p TOKEN=<"%TOKEN_FILE%"
)
if "%TOKEN%"=="" (
    echo Could not generate an API token.
    pause
    exit /b 1
)
echo Starting Bale branch API + UI on http://%HOST%:%PORT%/ui
echo UI token: %TOKEN%
".venv\Scripts\python.exe" -m eitaa_bridge.application.bale_client.api_server --host "%HOST%" --port %PORT% --token %TOKEN%
exit /b %ERRORLEVEL%
