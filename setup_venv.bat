@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PIP_PROGRESS_BAR=off"
cd /d "%~dp0"
set "SILENT=0"
set "REPAIR=0"
set "NEW_ENV=0"
for %%A in (%*) do (
  if /I "%%~A"=="/silent" set "SILENT=1"
  if /I "%%~A"=="/repair" set "REPAIR=1"
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating .venv with Python 3.13...
    py -3.13 -m venv .venv
    if errorlevel 1 (
        echo Python 3.13 x64 was not found.
        echo Install Python 3.13 x64, then run install_app.bat again.
        if "%SILENT%"=="0" pause
        exit /b 1
    )
    set "NEW_ENV=1"
) else (
    echo Existing .venv found.
)

set "PYTHON=.venv\Scripts\python.exe"
if not exist "vendor\eitaa_core-0.6.0.dev19-py3-none-any.whl" goto :missing
if not exist "dist\eitaa_bridge-0.7.0.dev31-py3-none-any.whl" goto :missing
if not exist "vendor\runtime\requests-2.34.2-py3-none-any.whl" goto :missing
if not exist "vendor\runtime\tzdata-2026.3-py2.py3-none-any.whl" goto :missing
if not exist "scripts\check_runtime_environment.py" goto :missing

if "%NEW_ENV%"=="0" if "%REPAIR%"=="0" (
  "%PYTHON%" "scripts\check_runtime_environment.py" >nul 2>nul
  if not errorlevel 1 goto :ready
)

if "%REPAIR%"=="1" goto :force_repair

echo Installing or updating only missing/mismatched bundled packages...
"%PYTHON%" -m pip install --no-index --find-links "vendor\runtime" --upgrade requests==2.34.2 tzdata==2026.3
if errorlevel 1 goto :failed
"%PYTHON%" -m pip install --no-index --no-deps --upgrade "vendor\eitaa_core-0.6.0.dev19-py3-none-any.whl" "dist\eitaa_bridge-0.7.0.dev31-py3-none-any.whl"
if errorlevel 1 goto :failed
"%PYTHON%" "scripts\check_runtime_environment.py" >nul
if errorlevel 1 goto :repair_required
goto :ready

:force_repair
echo Repairing the bundled backend environment...
"%PYTHON%" -m pip install --no-index --find-links "vendor\runtime" --force-reinstall requests==2.34.2 tzdata==2026.3
if errorlevel 1 goto :failed
"%PYTHON%" -m pip install --no-index --no-deps --force-reinstall "vendor\eitaa_core-0.6.0.dev19-py3-none-any.whl" "dist\eitaa_bridge-0.7.0.dev31-py3-none-any.whl"
if errorlevel 1 goto :failed
"%PYTHON%" "scripts\check_runtime_environment.py" >nul
if errorlevel 1 goto :failed

:ready
"%PYTHON%" -m pip check
if errorlevel 1 goto :failed
if not exist "bridge.json" copy /Y "bridge.example.json" "bridge.json" >nul
if not exist ".env" copy /Y ".env.example" ".env" >nul
if not exist "runtime\logs" mkdir "runtime\logs"
if not exist "backups\runtime" mkdir "backups\runtime"

echo.
echo Eitaa Bridge v0.7 UI MVP 6.1.1 Runtime environment is ready.
"%PYTHON%" --version
"%PYTHON%" -c "import eitaa_core,eitaa_bridge; print('Core:', eitaa_core.__version__); print('Bridge:', eitaa_bridge.__version__)"
if "%SILENT%"=="0" pause
exit /b 0

:repair_required
echo.
echo The existing environment has same-version damage that normal install will not overwrite.
echo Run repair_app.bat to perform an explicit repair after the owned runtime is stopped.
goto :failed

:missing
echo A bundled runtime file is missing. Re-extract the complete MVP 6.1.1 package.
goto :failed

:failed
echo.
echo Backend setup failed.
if "%SILENT%"=="0" pause
exit /b 1
