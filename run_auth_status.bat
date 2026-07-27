@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r=Invoke-RestMethod -Method Get -Uri 'http://127.0.0.1:8765/api/v1/auth/status' -TimeoutSec 10; $r | ConvertTo-Json -Depth 8 } catch { Write-Host 'Local API is unavailable:' $_.Exception.Message; exit 1 }"
set EXIT_CODE=%ERRORLEVEL%
pause
exit /b %EXIT_CODE%
