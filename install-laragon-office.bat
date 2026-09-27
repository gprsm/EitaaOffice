@echo off
REM =====================================================================
REM Laragon install + office vhost wiring for EitaaBridge (EitaaOffice)
REM Run this AFTER the BITS download of laragon-wamp.exe completes
REM (the download continues at OS level even if this session is closed;
REM  check progress in Windows Settings > BITS, or re-run this script).
REM Steps:
REM   1. wait for the full installer (239,751,056 bytes) via BITS
REM   2. silent-install Laragon into C:\laragon
REM   3. drop the office vhost (redirect :80 -> product origin)
REM   4. start Apache
REM   5. register Laragon in the Startup folder
REM =====================================================================
setlocal
set INSTALLER=C:\Users\mohse\Downloads\laragon-wamp.exe
set EXPECTED=239751056

:waitfile
if not exist "%INSTALLER%" (
    echo installer not found; BITS job may still be queued. Retrying in 30s...
    timeout /t 30 >nul
    goto waitfile
)
for /f %%S in ('powershell -NoProfile -Command "(Get-Item '%INSTALLER%').Length"') do set SIZE=%%S
echo current size: %SIZE% / %EXPECTED%
if %SIZE% LSS %EXPECTED% (
    echo download incomplete; restarting BITS transfer and re-checking in 60s...
    powershell -NoProfile -Command "$job = Get-BitsTransfer -ErrorAction SilentlyContinue | Where-Object DisplayName -eq 'Laragon 8.7.0 download'; if (-not $job) { Start-BitsTransfer -Source 'https://github.com/leokhoa/laragon/releases/download/8.7.0/laragon-wamp.exe' -Destination 'C:\Users\mohse\Downloads\laragon-wamp.exe' -DisplayName 'Laragon 8.7.0 download' -Asynchronous } else { $job | Where-Object {$_.JobState -ne 'Transferred'} | Resume-BitsTransfer }" >nul 2>&1
    timeout /t 60 >nul
    goto waitfile
)

echo Installing Laragon silently to C:\laragon ...
"%INSTALLER%" /S /D=C\laragon
timeout /t 20 >nul

echo Copying office vhost ...
if not exist "C:\laragon\etc\apache2\sites-enabled" mkdir "C:\laragon\etc\apache2\sites-enabled"
copy /Y "C:\Users\mohse\AppData\Local\Programs\EitaaBridge\deployment\laragon\office.conf" "C:\laragon\etc\apache2\sites-enabled\office.conf" >nul

echo Starting Apache ...
for /r "C:\laragon\bin\apache" %%H in (httpd.exe) do if exist "%%H" set HTTPD=%%H
if defined HTTPD (
    "%HTTPD%" -k start
    echo Apache started from: %HTTPD%
) else (
    echo httpd.exe not found under C:\laragon\bin\apache - start Apache from the Laragon tray menu once.
)

echo Registering Laragon autostart ...
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $startup = [Environment]::GetFolderPath('Startup'); $sc = $ws.CreateShortcut(\"$startup\Laragon.lnk\"); $sc.TargetPath = 'C:\laragon\laragon.exe'; $sc.WorkingDirectory = 'C:\laragon'; $sc.Save()"
echo Done. Test: http://eitaaoffice.test  (redirects to http://192.168.1.2:8765)
pause
