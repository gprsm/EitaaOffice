@echo off

setlocal EnableExtensions DisableDelayedExpansion

chcp 65001 >nul

set "PYTHONUTF8=1"

set "PYTHONIOENCODING=utf-8"

set "PIP_PROGRESS_BAR=off"

cd /d "%~dp0"

echo ================================================

echo  Eitaa Bridge MVP 6.1.1 Runtime Office Builder

echo ================================================

where py >nul 2>nul || goto :python_missing

for /f "usebackq delims=" %%P in (`py -3.13 -c "import sys; print(sys.base_prefix)"`) do set "PYROOT=%%P"

if not exist "%PYROOT%\python.exe" goto :python_missing

if not exist "dist\eitaa_bridge-0.7.0.dev31-py3-none-any.whl" goto :missing

if not exist "vendor\eitaa_core-0.6.0.dev19-py3-none-any.whl" goto :missing

if not exist "vendor\runtime\tzdata-2026.3-py2.py3-none-any.whl" goto :missing

if not exist "ui\dist\index.html" goto :missing

if not exist "scripts\write_iexpress_sed.py" goto :missing



set "BUILD=%TEMP%\EitaaBridgeOfficeBuild-%RANDOM%-%RANDOM%"

set "APP=%BUILD%\payload\app"

set "PORTABLE=%BUILD%\portable"

set "OUT=%CD%\release\office"

mkdir "%APP%" >nul 2>nul

mkdir "%PORTABLE%" >nul 2>nul

mkdir "%OUT%" >nul 2>nul



for %%F in (VERSION.txt bridge.example.json .env.example backup_now.bat restore_backup.bat create_diagnostics.bat open_runtime_logs.bat run_doctor.bat EitaaBridgeOffice.vbs stop_eitaa_bridge.bat) do copy /Y "%%F" "%APP%\%%F" >nul

for %%D in (dist vendor scripts docs) do robocopy "%%D" "%APP%\%%D" /E /R:2 /W:1 /NFL /NDL /NP /XD __pycache__ >nul

if errorlevel 8 goto :failed

mkdir "%APP%\ui" >nul 2>nul

robocopy "ui\dist" "%APP%\ui\dist" /E /R:2 /W:1 /NFL /NDL /NP >nul

if errorlevel 8 goto :failed



echo Copying portable Python 3.13 runtime...

robocopy "%PYROOT%" "%APP%\python" /E /R:2 /W:1 /NFL /NDL /NP /XD "%PYROOT%\Lib\site-packages" "%PYROOT%\Scripts" "%PYROOT%\include" "%PYROOT%\libs" __pycache__ /XF *.pyc >nul

if errorlevel 8 goto :failed



mkdir "%APP%\python-packages" >nul 2>nul

py -3.13 -m pip install --upgrade --no-index --find-links "vendor\runtime" --target "%APP%\python-packages" requests==2.34.2 tzdata==2026.3

if errorlevel 1 goto :failed

py -3.13 -m pip install --upgrade --no-index --no-deps --target "%APP%\python-packages" "vendor\eitaa_core-0.6.0.dev19-py3-none-any.whl" "dist\eitaa_bridge-0.7.0.dev31-py3-none-any.whl"

if errorlevel 1 goto :failed

set "PYTHONPATH=%APP%\python-packages"

"%PYROOT%\python.exe" "%APP%\scripts\check_runtime_environment.py"
if errorlevel 1 goto :failed
"%PYROOT%\python.exe" -c "import eitaa_core.infrastructure.diagnostics; import eitaa_bridge.infrastructure.diagnostics; print('Office diagnostics packages: OK')"

if errorlevel 1 goto :failed

set "PYTHONPATH="



rem Include current Session, database, settings, media and compositions.

set "BACKUPPY=py -3.13"

if exist ".venv\Scripts\python.exe" set "BACKUPPY=.venv\Scripts\python.exe"

%BACKUPPY% scripts\backup_runtime.py --output "%APP%\transfer-backup.zip" --quiet

if errorlevel 1 goto :failed



powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -LiteralPath '%APP%' -DestinationPath '%BUILD%\office_payload.zip' -CompressionLevel Optimal -Force"

if errorlevel 1 goto :failed

copy /Y "installer\install_office_payload.cmd" "%BUILD%\install_office_payload.cmd" >nul



rem Simulate the installer copy before publishing artifacts. This catches recursive

rem robocopy exclusions such as the previous diagnostics-package omission.

set "SIM=%BUILD%\install-simulation"

mkdir "%SIM%" >nul 2>nul

robocopy "%APP%" "%SIM%" /E /R:2 /W:1 /NFL /NDL /NP /XJ /XF bridge.json .env .eitaa_session.json composition.json transfer-backup.zip >nul

if errorlevel 8 goto :failed

set "PYTHONPATH=%SIM%\python-packages"

"%SIM%\python\python.exe" "%SIM%\scripts\check_runtime_environment.py"
if errorlevel 1 goto :failed
"%SIM%\python\python.exe" -c "import eitaa_core.infrastructure.diagnostics; import eitaa_bridge.infrastructure.diagnostics; print('Office install-copy simulation: OK')"

if errorlevel 1 goto :failed

set "PYTHONPATH="

copy /Y "%BUILD%\office_payload.zip" "%PORTABLE%\office_payload.zip" >nul

copy /Y "%BUILD%\install_office_payload.cmd" "%PORTABLE%\INSTALL_EITAA_BRIDGE_OFFICE.cmd" >nul

>"%PORTABLE%\README_FIRST.txt" echo Extract this ZIP, then run INSTALL_EITAA_BRIDGE_OFFICE.cmd.

>>"%PORTABLE%\README_FIRST.txt" echo No Python or Node.js installation is required on the office computer.



set "PORTABLEZIP=%OUT%\EitaaBridge-0.8.0-rc1-Office-Portable.zip"

powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '%PORTABLE%\*' -DestinationPath '%PORTABLEZIP%' -CompressionLevel Optimal -Force"

if errorlevel 1 goto :failed

certutil -hashfile "%PORTABLEZIP%" SHA256 > "%PORTABLEZIP%.sha256.txt"

echo.

echo Portable office installer created successfully:

echo %PORTABLEZIP%



rem Build the optional one-file Setup.exe. The SED is written as strict ASCII.

set "IEXPRESS=%SystemRoot%\System32\iexpress.exe"

set "SETUPTEMP=%BUILD%\EitaaBridge-0.8.0-rc1-Office-Setup-x64.exe"

set "SETUPEXE=%OUT%\EitaaBridge-0.8.0-rc1-Office-Setup-x64.exe"

set "SED=%BUILD%\office_setup.sed"

if not exist "%IEXPRESS%" goto :portable_only

py -3.13 scripts\write_iexpress_sed.py --output "%SED%" --source-dir "%BUILD%" --target-exe "%SETUPTEMP%"

if errorlevel 1 goto :portable_only

"%IEXPRESS%" /N /Q "%SED%"

if errorlevel 1 goto :portable_only

if not exist "%SETUPTEMP%" goto :portable_only

copy /Y "%SETUPTEMP%" "%SETUPEXE%" >nul

certutil -hashfile "%SETUPEXE%" SHA256 > "%SETUPEXE%.sha256.txt"

echo.

echo One-file Setup created successfully:

echo %SETUPEXE%

goto :success



:portable_only

echo.

echo WARNING: IExpress could not create the one-file Setup.exe.

echo The portable installer ZIP was created successfully and is fully usable today.

echo Extract it on the office computer and run INSTALL_EITAA_BRIDGE_OFFICE.cmd.

goto :success



:success

echo.

echo IMPORTANT: These files contain your Eitaa Session and local data.

echo Keep them private and delete removable-media copies after installation.

rmdir /S /Q "%BUILD%" >nul 2>nul

pause

exit /b 0



:python_missing

echo Python 3.13 x64 was not found on this build computer.

goto :failed_pause

:missing

echo A required MVP 6.1.1 Runtime file is missing. Re-extract the complete final package and run the builder again.

goto :failed_pause

:failed

echo.

echo Build failed. Temporary files remain at: %BUILD%

:failed_pause

pause

exit /b 1
