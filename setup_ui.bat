@echo off
setlocal
cd /d "%~dp0"
set "SILENT=0"
if /I "%~1"=="/silent" set "SILENT=1"

where node >nul 2>nul
if errorlevel 1 (
    echo Node.js LTS was not found.
    echo Install Node.js 24 LTS x64, then run this file again.
    if "%SILENT%"=="0" pause
    exit /b 1
)
where npm.cmd >nul 2>nul
if errorlevel 1 (
    echo npm.cmd was not found.
    if "%SILENT%"=="0" pause
    exit /b 1
)

cd /d "%~dp0ui"
if not exist "public\fonts" mkdir "public\fonts"
set "FONT_READY=0"
if exist "fonts\IRANSansWeb-Regular.woff2" (
    copy /Y "fonts\IRANSansWeb-Regular.woff2" "public\fonts\IRANSansWeb-Regular.woff2" >nul
    set "FONT_READY=1"
)
if exist "fonts\IRANSansWeb-Bold.woff2" (
    copy /Y "fonts\IRANSansWeb-Bold.woff2" "public\fonts\IRANSansWeb-Bold.woff2" >nul
    set "FONT_READY=1"
)
if exist "fonts\IRANSansWeb.woff2" (
    copy /Y "fonts\IRANSansWeb.woff2" "public\fonts\IRANSansWeb.woff2" >nul
    set "FONT_READY=1"
)
if "%FONT_READY%"=="1" (
    echo IRANSans font files detected and prepared.
) else (
    echo Optional IRANSans fonts were not found at ui\fonts; fallback fonts will be used.
)
echo Installing Eitaa Bridge UI dependencies from the public npm registry...
set "npm_config_registry=https://registry.npmjs.org/"
set "npm_config_audit=false"
set "npm_config_fund=false"
set "npm_config_fetch_retries=4"
set "npm_config_fetch_timeout=300000"

rem Material UI dependencies are installed from the public registry. npm install also refreshes the lock file when this source handoff adds UI packages.
call npm.cmd install --registry=https://registry.npmjs.org/ --no-audit --no-fund --prefer-offline
if errorlevel 1 goto :install_failed

echo Verifying TypeScript before the production build...
call npm.cmd run check
if errorlevel 1 goto :typecheck_failed

echo Building the production UI...
call npm.cmd run build
if errorlevel 1 goto :build_failed

if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" "%~dp0scripts\sync_ui_fonts.py" --quiet
    if errorlevel 1 goto :failed
)

echo.
echo Eitaa Bridge desktop UI is ready.
node --version
call npm.cmd --version
if "%SILENT%"=="0" pause
exit /b 0

:install_failed
echo.
echo UI dependency installation failed.
echo npm could not prepare the project dependencies. Check registry or proxy access and review the npm error above.
goto :failure_exit

:typecheck_failed
echo.
echo UI TypeScript validation failed.
echo This is a source-code error, not a registry or internet error. Review the TypeScript diagnostics above.
goto :failure_exit

:build_failed
echo.
echo UI production build failed after TypeScript validation.
echo Review the Vite or finalize-build diagnostics above.
goto :failure_exit

:failed
echo.
echo UI setup failed during local preparation. Review the message above.
goto :failure_exit

:failure_exit
if "%SILENT%"=="0" pause
exit /b 1
