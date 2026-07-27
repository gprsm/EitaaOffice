@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run setup_venv.bat first.
    pause
    exit /b 1
)
if "%~1"=="" (
    echo Usage: run_wp_tags.bat SITE_KEY_OR_default [SEARCH]
    pause
    exit /b 2
)
set "SITE_ARG="
if /I not "%~1"=="default" set "SITE_ARG=--site-key %~1"
set "SEARCH_ARG="
if not "%~2"=="" set SEARCH_ARG=--search "%~2"
".venv\Scripts\python.exe" -m eitaa_bridge.interfaces.cli --config bridge.json %SITE_ARG% wp tags %SEARCH_ARG%
set EXIT_CODE=%ERRORLEVEL%
pause
exit /b %EXIT_CODE%
