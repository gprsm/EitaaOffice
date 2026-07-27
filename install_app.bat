@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"
echo =============================================
echo   Eitaa Bridge v0.7 UI MVP 6.1.1 Setup
echo =============================================
echo.
call stop_eitaa_bridge.bat /quiet >nul 2>nul
if errorlevel 1 goto :stop_failed
call setup_venv.bat /silent
if errorlevel 1 goto :failed
rem Node.js, npm packages, and Electron are development-only when a valid prebuilt Material UI runtime is bundled.
if exist "EitaaBridge-win32-x64\EitaaBridge.exe" (
  echo Packaged desktop runtime detected; Node.js setup is not required.
) else if exist "EitaaBridge.exe" (
  echo Packaged desktop runtime detected; Node.js setup is not required.
) else if exist "ui\dist\index.html" (
  if exist "ui\dist\.material-ui-v1" (
    echo Material UI production build is already available in ui\dist.
    ".venv\Scripts\python.exe" scripts\sync_ui_fonts.py --quiet
    if errorlevel 1 goto :failed
    if not exist "ui\dist\fonts\IRANSansWeb-Regular.woff2" (
      echo Optional licensed IRANSans files are incomplete or absent; Windows fallback fonts will be used.
    ) else if not exist "ui\dist\fonts\IRANSansWeb-Bold.woff2" (
      echo Optional licensed IRANSans files are incomplete or absent; Windows fallback fonts will be used.
    ) else (
      echo Optional licensed IRANSans Regular and Bold fonts are ready.
    )
  ) else (
    echo Existing UI build is from the legacy design and will not be used.
    call setup_ui.bat /silent
    if errorlevel 1 goto :failed
  )
) else (
  call setup_ui.bat /silent
  if errorlevel 1 goto :failed
)
if exist "bridge.json" (
  ".venv\Scripts\python.exe" scripts\backup_runtime.py --without-media --quiet >nul 2>nul
)
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\create_shortcuts.ps1" -Root "%~dp0" >nul
if errorlevel 1 echo Warning: shortcuts could not be created; EitaaBridge.bat remains available.
echo.
echo Installation completed without force-reinstalling a healthy environment.
echo Start Eitaa Bridge from the Desktop, Start Menu, or EitaaBridge.bat.
pause
exit /b 0
:stop_failed
echo.
echo The owned runtime could not be stopped safely. No package files were changed.
goto :failed
:failed
echo.
echo Installation failed. Review the message above.
pause
exit /b 1
