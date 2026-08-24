@echo off
setlocal
cd /d "%~dp0"

rem Pin the current Flash model for the G8 pilot.
set "G8_MAPPING_MODEL=gemini-3.6-flash"
set "DIVERSE_OUT=.local\stage5_g8_mapping_pilot\diverse20"

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
echo MathAI Stage 5B-2A - G8 Diverse 20 Smoke Test
echo 8 square-difference + 6 radicals + 6 other strata
echo LOCAL ONLY / NO PRODUCTION WRITES
echo ================================================

%PY% scripts\stage5_g8_diverse_smoke.py
if errorlevel 1 goto :fail

%PY% scripts\stage5_g8_mapping_pilot.py map --output "%DIVERSE_OUT%" --model %G8_MAPPING_MODEL%
if errorlevel 1 goto :fail

%PY% scripts\stage5_g8_mapping_pilot.py validate --output "%DIVERSE_OUT%"
if errorlevel 1 goto :fail

echo.
echo Diversified 20-question mapping smoke completed.
echo Review: %DIVERSE_OUT%\g8_human_review_queue.csv
echo Manifest: %DIVERSE_OUT%\diverse_smoke_manifest.json
pause
exit /b 0

:fail
echo.
echo Diverse mapping smoke FAILED or BLOCKED. Production was not modified.
pause
exit /b 1
