@echo off
setlocal
cd /d "%~dp0"

rem Pin the current Flash model for the G8 pilot.
set "G8_MAPPING_MODEL=gemini-3.6-flash"
set "SCOPE_OUT=.local\stage5_g8_mapping_pilot\scope20"

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else if exist "..\.venv\Scripts\python.exe" (
  set "PY=..\.venv\Scripts\python.exe"
) else if exist "C:\MathAI\.venv\Scripts\python.exe" (
  set "PY=C:\MathAI\.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

echo ================================================
echo MathAI Stage 5B-2A - G8 Scope-aware Diverse 20
echo 8 square-difference + 6 radicals + 6 other strata
echo Scope gate first; map only true G8 questions
echo LOCAL ONLY / NO PRODUCTION WRITES
echo ================================================

%PY% scripts\stage5_g8_diverse_smoke.py --target-name scope20
if errorlevel 1 goto :fail

%PY% scripts\stage5_g8_scope_mapping.py map --output "%SCOPE_OUT%" --model %G8_MAPPING_MODEL%
if errorlevel 1 goto :fail

%PY% scripts\stage5_g8_scope_mapping.py validate --output "%SCOPE_OUT%"
if errorlevel 1 goto :fail

echo.
echo Scope-aware diversified 20-question smoke completed.
echo Review: %SCOPE_OUT%\g8_scope_human_review_queue.csv
echo Report: %SCOPE_OUT%\scope_validation_report.json
pause
exit /b 0

:fail
echo.
echo Scope-aware mapping smoke FAILED or BLOCKED. Production was not modified.
pause
exit /b 1
