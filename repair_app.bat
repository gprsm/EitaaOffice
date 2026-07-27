@echo off
setlocal
cd /d "%~dp0"
echo =============================================
echo   Eitaa Bridge explicit backend repair
echo =============================================
echo.
call stop_eitaa_bridge.bat /quiet
if errorlevel 1 goto :failed
call setup_venv.bat /repair /silent
if errorlevel 1 goto :failed
echo.
echo Repair completed. Runtime data and UI files were not intentionally replaced.
pause
exit /b 0
:failed
echo.
echo Repair failed. Review runtime\logs and the messages above.
pause
exit /b 1
