@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else if exist "..\.venv\Scripts\python.exe" (
  set "PY=..\.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

%PY% scripts\stage5_g8_mapping_pilot.py map --limit 20
if errorlevel 1 goto :fail
%PY% scripts\stage5_g8_mapping_pilot.py validate
if errorlevel 1 goto :fail

echo.
echo 20-question mapping smoke completed.
echo Review: .local\stage5_g8_mapping_pilot\g8_human_review_queue.csv
pause
exit /b 0

:fail
echo.
echo Mapping smoke FAILED or BLOCKED. Production was not modified.
pause
exit /b 1
