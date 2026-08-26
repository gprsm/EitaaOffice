@echo off
setlocal
cd /d "%~dp0"
echo =============================================
echo  Eitaa Bridge v0.8 RC1 Windows Installer Build
echo =============================================
where npm.cmd >nul 2>nul || goto :node_missing
where py >nul 2>nul || goto :python_missing
pushd ui
call npm.cmd ci --registry=https://registry.npmjs.org/ --no-audit --no-fund
if errorlevel 1 goto :ui_failed
call npm.cmd run pack:win
if errorlevel 1 goto :ui_failed
popd
py -3.13 scripts\prepare_windows_release.py
if errorlevel 1 goto :failed
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" goto :inno_missing
"%ISCC%" installer\EitaaBridge.iss
if errorlevel 1 goto :failed
echo.
echo Installer created under release\installer.
pause
exit /b 0
:ui_failed
popd
:failed
echo Build failed. Review the output above.
pause
exit /b 1
:node_missing
echo Node.js 24 LTS x64 is required for the installer build workstation.
pause
exit /b 1
:python_missing
echo Python 3.13 x64 is required for the installer build workstation.
pause
exit /b 1
:inno_missing
echo Inno Setup 6 was not found. Install it, then run this file again.
pause
exit /b 1
