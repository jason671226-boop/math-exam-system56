@echo off
setlocal
cd /d "%~dp0"

set "G8_MAPPING_MODEL=gemini-3.6-flash"
set "SOURCE_OUT=.local\stage5_g8_mapping_pilot"
set "FULL_OUT=%SOURCE_OUT%\scope200"

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else if exist "..\.venv\Scripts\python.exe" (
  set "PY=..\.venv\Scripts\python.exe"
) else if exist "C:\MathAI\.venv\Scripts\python.exe" (
  set "PY=C:\MathAI\.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

echo =====================================================
echo MathAI Stage 5B-2B - G8 Full 200 Scope-aware Pilot
echo Scope gate first; map only true G8 questions
echo LOCAL ONLY / NO PRODUCTION READS OR WRITES
echo Resumable: rerun this same BAT after any interruption
echo =====================================================

if not exist "%SOURCE_OUT%\g8_pilot_sample.json" goto :missing
if not exist "%SOURCE_OUT%\g8_mapping_input.jsonl" goto :missing
if not exist "%SOURCE_OUT%\g8_curriculum_skills.json" goto :missing
if not exist "%SOURCE_OUT%\g8_curriculum_micro_skills.json" goto :missing

if not exist "%FULL_OUT%" mkdir "%FULL_OUT%"
copy /Y "%SOURCE_OUT%\g8_pilot_sample.json" "%FULL_OUT%\g8_pilot_sample.json" >nul
copy /Y "%SOURCE_OUT%\g8_mapping_input.jsonl" "%FULL_OUT%\g8_mapping_input.jsonl" >nul
copy /Y "%SOURCE_OUT%\g8_curriculum_skills.json" "%FULL_OUT%\g8_curriculum_skills.json" >nul
copy /Y "%SOURCE_OUT%\g8_curriculum_micro_skills.json" "%FULL_OUT%\g8_curriculum_micro_skills.json" >nul

%PY% scripts\stage5_g8_scope_full.py all --output "%FULL_OUT%" --model %G8_MAPPING_MODEL%
if errorlevel 1 goto :fail

echo.
echo Full 200-question scope-aware pilot completed.
echo Review: %FULL_OUT%\g8_scope_human_review_queue.csv
echo Report: %FULL_OUT%\scope_validation_report.json
pause
exit /b 0

:missing
echo.
echo Required prepared 200-row local pilot artifacts are missing.
echo Run Stage5_G8_Pilot_準備.bat first. Production was not modified.
pause
exit /b 2

:fail
echo.
echo Full 200 scope pilot FAILED or was interrupted.
echo Completed rows were checkpointed locally. Rerun this same BAT to resume.
echo Production was not modified.
pause
exit /b 1
