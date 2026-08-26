@echo off
setlocal
cd /d "%~dp0"
set "QUIET="
if /I "%~1"=="/quiet" set "QUIET=--quiet"
set "PYTHON="
if exist "python\python.exe" (
  set "PYTHON=python\python.exe"
  set "PYTHONPATH=%CD%\python-packages"
) else if exist ".venv\Scripts\python.exe" (
  set "PYTHON=.venv\Scripts\python.exe"
) else (
  where py >nul 2>nul || goto :missing
  set "PYTHON=py -3.13"
)
%PYTHON% "scripts\office_runtime.py" stop --root "%CD%" --allow-legacy-owned %QUIET%
set "RESULT=%ERRORLEVEL%"
set "PYTHONPATH="
exit /b %RESULT%
:missing
if not defined QUIET echo Python runtime was not found; no owned process was stopped.
exit /b 1
