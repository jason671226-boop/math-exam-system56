@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "LOCAL_ROOT=.local\stage5_g8_mapping_pilot"

python scripts\stage5_g8_coverage.py --scope-dir "%LOCAL_ROOT%\scope200" --output "%LOCAL_ROOT%\freeze"
if errorlevel 1 exit /b %errorlevel%

python scripts\stage5_g8_cross_unit_validation.py all --output "%LOCAL_ROOT%\cross_unit" --model gemini-3.6-flash --scope-results "%LOCAL_ROOT%\scope200\g8_scope_mapping_results.jsonl"
if errorlevel 1 exit /b %errorlevel%

python scripts\stage5_g8_freeze_handoff.py --local-root "%LOCAL_ROOT%" --destination "docs\stage5\G8_PILOT_FREEZE_HANDOFF.md"
if errorlevel 1 exit /b %errorlevel%

echo G8 PILOT FOUNDATION: SAFE TO FREEZE
exit /b 0
