@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PIP_PROGRESS_BAR=off"
set "NO_PAUSE=0"
if /I "%~1"=="/quiet" set "NO_PAUSE=1"
cd /d "%~dp0"

echo ================================================
echo  Eitaa Bridge self-contained Windows builder
echo ================================================

rem Python is required only on this build computer. The generated installer
rem carries its own application-local Python runtime for the destination PC.
set "BUILDPY="
if exist ".venv\Scripts\python.exe" set "BUILDPY=%CD%\.venv\Scripts\python.exe"
if not defined BUILDPY (
  where python.exe >nul 2>nul || goto :python_missing
  for /f "usebackq delims=" %%P in (`where python.exe`) do if not defined BUILDPY set "BUILDPY=%%P"
)
"%BUILDPY%" -c "import struct,sys; raise SystemExit(0 if sys.version_info[:2] == (3,13) and struct.calcsize('P') == 8 else 1)"
if errorlevel 1 goto :python_missing
set "PYROOTFILE=%TEMP%\EitaaBridgePythonRoot-%RANDOM%-%RANDOM%.txt"
"%BUILDPY%" -c "import sys; print(sys.base_prefix)" > "%PYROOTFILE%"
if errorlevel 1 goto :python_missing
set /p "PYROOT="<"%PYROOTFILE%"
del /Q "%PYROOTFILE%" >nul 2>nul
if not exist "%PYROOT%\python.exe" goto :python_missing
if not exist "VERSION.txt" goto :missing
if not exist "bridge.example.json" goto :missing
if not exist ".env.example" goto :missing
if not exist "vendor\eitaa_core-0.6.0.dev19-py3-none-any.whl" goto :missing
if not exist "vendor\runtime\tzdata-2026.3-py2.py3-none-any.whl" goto :missing
if not exist "vendor\runtime\cryptography-46.0.7-cp311-abi3-win_amd64.whl" goto :missing
if not exist "vendor\runtime\cffi-2.1.1-cp313-cp313-win_amd64.whl" goto :missing
if not exist "vendor\runtime\pycparser-3.0-py3-none-any.whl" goto :missing
if not exist "ui\dist\index.html" goto :missing
if not exist "ui\dist\.material-ui-v1" goto :missing
if not exist "scripts\write_iexpress_sed.py" goto :missing
if not exist "scripts\build_self_contained_setup.py" goto :missing
if not exist "scripts\check_office_payload_privacy.py" goto :missing
if not exist "scripts\archive_previous_office_release.ps1" goto :missing
if not exist "scripts\sign_windows_release.ps1" goto :missing
if not exist "scripts\verify_windows_release_signature.ps1" goto :missing
if not exist "installer\check_windows_version.vbs" goto :missing
if not exist "installer\license-policy.json" goto :missing
set "SETUPICON=%CD%\installer\assets\EitaaBridge.ico"
if not exist "%SETUPICON%" goto :icon_missing
if not defined EITAA_CODE_SIGNING_THUMBPRINT goto :signing_missing

echo Rebuilding and verifying the bundled Bridge wheel...
"%BUILDPY%" scripts\build_wheel_stdlib.py --root "%CD%" --output-dir "%CD%\dist" --force
if errorlevel 1 goto :failed
"%BUILDPY%" package_clean.py --root "%CD%" --dry-run
if errorlevel 1 goto :failed

set "BUILD=%TEMP%\EitaaBridgeOfficeBuild-%RANDOM%-%RANDOM%"
set "APP=%BUILD%\payload\app"
set "PORTABLE=%BUILD%\portable"
set "OUT=%CD%\release\office"
mkdir "%APP%" >nul 2>nul
mkdir "%PORTABLE%" >nul 2>nul
mkdir "%OUT%" >nul 2>nul
if not exist "%APP%" goto :failed

for %%F in (VERSION.txt bridge.example.json .env.example backup_now.bat restore_backup.bat create_diagnostics.bat open_runtime_logs.bat run_doctor.bat EitaaBridgeOffice.vbs stop_eitaa_bridge.bat) do (
  if not exist "%%F" goto :missing
  copy /Y "%%F" "%APP%\%%F" >nul || goto :failed
)
copy /Y "installer\license-policy.json" "%APP%\license-policy.json" >nul || goto :failed
mkdir "%APP%\assets" >nul 2>nul
copy /Y "%SETUPICON%" "%APP%\assets\EitaaBridge.ico" >nul || goto :failed

for %%D in (dist vendor) do (
  robocopy "%%D" "%APP%\%%D" /E /R:2 /W:1 /NFL /NDL /NP /XD __pycache__ >nul
  if errorlevel 8 goto :failed
)

mkdir "%APP%\scripts" >nul 2>nul
for %%F in (backup_runtime.py check_runtime_environment.py create_diagnostics_bundle.py doctor.py office_runtime.py restore_runtime.py runtime_state.py scan_diagnostics_bundle.py) do (
  if not exist "scripts\%%F" goto :missing
  copy /Y "scripts\%%F" "%APP%\scripts\%%F" >nul || goto :failed
)

mkdir "%APP%\docs" >nul 2>nul
for %%F in (BACKUP_RESTORE.md OFFICE_DEPLOYMENT.md OFFLINE_ACTIVATION.md RUNTIME_OWNERSHIP.md SECURITY.md) do (
  if not exist "docs\%%F" goto :missing
  copy /Y "docs\%%F" "%APP%\docs\%%F" >nul || goto :failed
)

mkdir "%APP%\ui" >nul 2>nul
robocopy "ui\dist" "%APP%\ui\dist" /E /R:2 /W:1 /NFL /NDL /NP /XJ >nul
if errorlevel 8 goto :failed

echo Copying the application-local Python 3.13 runtime...
robocopy "%PYROOT%" "%APP%\python" /E /R:2 /W:1 /NFL /NDL /NP /XJ /XD "%PYROOT%\Lib\site-packages" "%PYROOT%\Scripts" "%PYROOT%\include" "%PYROOT%\libs" "%PYROOT%\Doc" __pycache__ /XF *.pyc >nul
if errorlevel 8 goto :failed

mkdir "%APP%\python-packages" >nul 2>nul
"%BUILDPY%" -m pip install --upgrade --no-index --find-links "vendor\runtime" --target "%APP%\python-packages" requests==2.34.2 tzdata==2026.3 cryptography==46.0.7 cffi==2.1.1 pycparser==3.0
if errorlevel 1 goto :failed
"%BUILDPY%" -m pip install --upgrade --no-index --no-deps --target "%APP%\python-packages" "vendor\eitaa_core-0.6.0.dev19-py3-none-any.whl" "dist\eitaa_bridge-0.7.0.dev31-py3-none-any.whl"
if errorlevel 1 goto :failed

set "PYTHONPATH=%APP%\python-packages"
"%APP%\python\python.exe" "%APP%\scripts\check_runtime_environment.py"
if errorlevel 1 goto :failed
"%APP%\python\python.exe" -c "import eitaa_core.infrastructure.diagnostics; import eitaa_bridge.infrastructure.diagnostics; print('Office diagnostics packages: OK')"
if errorlevel 1 goto :failed
set "PYTHONPATH="

rem The shareable installer must never contain this computer's private state.
for %%F in (bridge.json .env .eitaa_session.json composition.json transfer-backup.zip) do if exist "%APP%\%%F" goto :privacy_failed
for /R "%APP%" %%F in (*private*key* *signing*key*) do if exist "%%F" goto :privacy_failed
for %%D in (data runtime diagnostics backups catalog) do if exist "%APP%\%%D" goto :privacy_failed
"%BUILDPY%" scripts\check_office_payload_privacy.py --root "%APP%"
if errorlevel 1 goto :privacy_failed

powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -LiteralPath '%APP%' -DestinationPath '%BUILD%\office_payload.zip' -CompressionLevel Optimal -Force"
if errorlevel 1 goto :failed
copy /Y "installer\install_office_payload.cmd" "%BUILD%\install_office_payload.cmd" >nul || goto :failed
copy /Y "installer\check_windows_version.vbs" "%BUILD%\check_windows_version.vbs" >nul || goto :failed

rem Simulate the managed install copy and validate the exact bundled runtime.
set "SIM=%BUILD%\install-simulation"
mkdir "%SIM%" >nul 2>nul
robocopy "%APP%" "%SIM%" /E /R:2 /W:1 /NFL /NDL /NP /XJ >nul
if errorlevel 8 goto :failed
set "PYTHONPATH=%SIM%\python-packages"
"%SIM%\python\python.exe" "%SIM%\scripts\check_runtime_environment.py"
if errorlevel 1 goto :failed
"%SIM%\python\python.exe" -c "import eitaa_core.infrastructure.diagnostics; import eitaa_bridge.infrastructure.diagnostics; print('Office install-copy simulation: OK')"
if errorlevel 1 goto :failed
set "PYTHONPATH="

copy /Y "%BUILD%\office_payload.zip" "%PORTABLE%\office_payload.zip" >nul || goto :failed
copy /Y "%BUILD%\install_office_payload.cmd" "%PORTABLE%\INSTALL_EITAA_BRIDGE_OFFICE.cmd" >nul || goto :failed
copy /Y "%BUILD%\check_windows_version.vbs" "%PORTABLE%\check_windows_version.vbs" >nul || goto :failed
>"%PORTABLE%\README_FIRST.txt" echo Extract this ZIP, then run INSTALL_EITAA_BRIDGE_OFFICE.cmd.
>>"%PORTABLE%\README_FIRST.txt" echo Windows 10 or newer x64 is required. Python and Node.js are bundled or unnecessary.

rem Preserve all previous release artifacts and checksums before publishing the new pair.
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\archive_previous_office_release.ps1" -ReleaseDirectory "%OUT%"
if errorlevel 1 goto :failed

set "PORTABLEZIP=%OUT%\EitaaBridge-0.8.0-rc6a-AuthChildRpc-SelfContained-Portable.zip"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '%PORTABLE%\*' -DestinationPath '%PORTABLEZIP%' -CompressionLevel Optimal -Force"
if errorlevel 1 goto :failed
certutil -hashfile "%PORTABLEZIP%" SHA256 > "%PORTABLEZIP%.sha256.txt"
echo.
echo Portable fallback created:
echo %PORTABLEZIP%

rem A branded Setup requires the .NET Framework compiler so the supplied ICO
rem is embedded in the executable. An unbranded IExpress fallback is not published.
set "SETUPEXE=%OUT%\EitaaBridge-0.8.0-rc6a-AuthChildRpc-InternalSigned-GuiSetup-x64.exe"
"%BUILDPY%" scripts\build_self_contained_setup.py --payload "%BUILD%\office_payload.zip" --installer "%BUILD%\install_office_payload.cmd" --preflight "%BUILD%\check_windows_version.vbs" --icon "%SETUPICON%" --output "%SETUPEXE%"
if errorlevel 1 goto :failed

echo Signing Setup with the internal publisher certificate...
if defined EITAA_TIMESTAMP_SERVER (
  powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\sign_windows_release.ps1" -Path "%SETUPEXE%" -Thumbprint "%EITAA_CODE_SIGNING_THUMBPRINT%" -TimestampServer "%EITAA_TIMESTAMP_SERVER%"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\sign_windows_release.ps1" -Path "%SETUPEXE%" -Thumbprint "%EITAA_CODE_SIGNING_THUMBPRINT%"
)
if errorlevel 1 goto :failed
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\verify_windows_release_signature.ps1" -Path "%SETUPEXE%" -ExpectedThumbprint "%EITAA_CODE_SIGNING_THUMBPRINT%" -TestTamperDetection
if errorlevel 1 goto :failed
echo.
echo Branded and internally signed one-file Setup created:
echo %SETUPEXE%
goto :success

:portable_only
echo.
echo WARNING: IExpress could not create the one-file Setup.exe.
echo The self-contained portable ZIP remains usable.
goto :success

:icon_missing
echo The required application icon was not found:
echo %SETUPICON%
echo Provide a multi-resolution ICO before building the branded Setup.
goto :failed_pause

:signing_missing
echo EITAA_CODE_SIGNING_THUMBPRINT is not set.
echo Create/select the internal code-signing certificate before building a release.
goto :failed_pause

:success
echo.
echo The outputs contain no session, live configuration, database, media, or logs.
rmdir /S /Q "%BUILD%" >nul 2>nul
if "%NO_PAUSE%"=="0" pause
exit /b 0

:privacy_failed
echo The staging payload unexpectedly contains private runtime state. Build stopped.
goto :failed

:python_missing
echo Python 3.13 x64 was not found on this build computer.
goto :failed_pause

:missing
echo A required release file is missing. Re-extract the complete package and try again.
goto :failed_pause

:failed
echo.
echo Build failed. Temporary files remain at: %BUILD%

:failed_pause
if "%NO_PAUSE%"=="0" pause
exit /b 1
