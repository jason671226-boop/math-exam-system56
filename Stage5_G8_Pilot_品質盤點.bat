@echo off
setlocal
cd /d "%~dp0"

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
echo MathAI Stage 5B-2C - G8 200 Quality Audit
echo LOCAL ONLY / NO PRODUCTION READS OR WRITES
echo ================================================

%PY% scripts\stage5_g8_scope_audit.py
if errorlevel 1 goto :fail

echo.
echo G8 quality audit completed.
echo Open these files if needed:
echo .local\stage5_g8_mapping_pilot\scope200\g8_scope_quality_summary.json
echo .local\stage5_g8_mapping_pilot\scope200\g8_scope_skill_distribution.csv
echo .local\stage5_g8_mapping_pilot\scope200\g8_scope_micro_distribution.csv
echo .local\stage5_g8_mapping_pilot\scope200\g8_scope_out_of_scope_10.csv
echo .local\stage5_g8_mapping_pilot\scope200\g8_scope_quality_flags.csv
pause
exit /b 0

:fail
echo.
echo G8 quality audit FAILED. Production was not modified.
pause
exit /b 1
