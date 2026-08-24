@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo MathAI Stage 5B-2A - G8 Local Mapping Pilot
echo READ-ONLY Production extract / NO DB WRITES
echo ================================================

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else if exist "..\.venv\Scripts\python.exe" (
  set "PY=..\.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

%PY% scripts\stage5_g8_mapping_pilot.py prepare --sample-size 200
if errorlevel 1 goto :fail

echo.
echo G8 Pilot prepare completed.
echo Output: .local\stage5_g8_mapping_pilot
pause
exit /b 0

:fail
echo.
echo G8 Pilot prepare FAILED or BLOCKED. Production was not modified.
pause
exit /b 1
