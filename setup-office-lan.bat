@echo off
REM =====================================================================
REM EitaaOffice LAN setup — one-click elevated step
REM Adds Windows Firewall inbound rules for the office product:
REM   - TCP 8765 : the EitaaBridge API/UI server (trusted_lan_http)
REM   - TCP 80   : Laragon Apache (friendly redirect)
REM Scope is deliberately minimal: Private profile + LocalSubnet only.
REM Auto-elevates via UAC; approve the prompt once.
REM =====================================================================
setlocal
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator rights...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo Adding firewall rules (Private profile, LocalSubnet only)...
netsh advfirewall firewall add rule name="EitaaBridge Office LAN 8765" dir=in action=allow protocol=TCP localport=8765 profile=private remoteip=localsubnet
netsh advfirewall firewall add rule name="EitaaBridge Office LAN 80 (Laragon)" dir=in action=allow protocol=TCP localport=80 profile=private remoteip=localsubnet


echo Marking the office Ethernet connection as Private network...
powershell -NoProfile -Command "Set-NetConnectionProfile -InterfaceAlias 'Ethernet' -NetworkCategory Private"

echo Adding hosts entry for eitaaoffice.test...
findstr /C:"eitaaoffice.test" C:\Windows\System32\drivers\etc\hosts >nul 2>&1
if %errorlevel% neq 0 (
    echo 192.168.1.2 eitaaoffice.test >> C:\Windows\System32\drivers\etc\hosts
)

echo.
echo Done. LAN users can open: http://192.168.1.2:8765
pause
