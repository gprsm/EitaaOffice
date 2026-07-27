@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
    echo Usage: upgrade_from_wordpress_update1_2.bat "PATH_TO_eitaa_bridge_v0_4_wordpress_update1_2"
    pause
    exit /b 2
)
set "SOURCE=%~f1"
if not exist "%SOURCE%\bridge.json" (
    echo Source bridge.json was not found.
    pause
    exit /b 1
)
copy /Y "%SOURCE%\bridge.json" "bridge.json" >nul
if exist "%SOURCE%\.env" copy /Y "%SOURCE%\.env" ".env" >nul
if not exist "data" mkdir "data"
echo Configuration and credentials were copied. install_app.bat installs the bundled Core 7.4.4 Wheel.
echo Run setup_venv.bat, run_tests.bat, and run_doctor.bat next.
pause
exit /b 0
