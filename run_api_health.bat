@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run setup_venv.bat first.
    pause
    exit /b 1
)
set "PORT=8765"
if not "%~1"=="" set "PORT=%~1"
".venv\Scripts\python.exe" -c "import json,requests; r=requests.get('http://127.0.0.1:%PORT%/api/v1/health',timeout=5); print(json.dumps(r.json(),ensure_ascii=False,indent=2)); raise SystemExit(0 if r.ok else 1)"
set EXIT_CODE=%ERRORLEVEL%
pause
exit /b %EXIT_CODE%
