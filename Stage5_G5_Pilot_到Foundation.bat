@echo off
setlocal
cd /d "%~dp0"

if /I not "%CD%"=="C:\MathAI_G5_Pilot" exit /b 20
for /f "delims=" %%B in ('git branch --show-current') do set "PILOT_BRANCH=%%B"
if /I not "%PILOT_BRANCH%"=="stage5/g5-mapping-pilot" exit /b 21

python scripts\stage5_g5_foundation.py audit || exit /b 2
python scripts\stage5_g5_foundation.py inventory || exit /b 3
python scripts\stage5_g5_foundation.py coverage || exit /b 4
python scripts\stage5_g5_foundation.py prepare --set tuning || exit /b 5
python scripts\stage5_g5_foundation.py map --set tuning || exit /b 7
python scripts\stage5_g5_foundation.py validate --set tuning || exit /b 8
python scripts\stage5_g5_foundation.py prepare --set holdout || exit /b 6
python scripts\stage5_g5_foundation.py map --set holdout || exit /b 9
python scripts\stage5_g5_foundation.py validate --set holdout || exit /b 10
python scripts\stage5_g5_foundation.py quality --set holdout || exit /b 11
python scripts\stage5_g5_foundation.py prepare-real || exit /b 12
python scripts\stage5_g5_foundation.py map-real || exit /b 13
python scripts\stage5_g5_foundation.py validate-real || exit /b 14
python -m pytest -q tests\test_stage5_g5_foundation.py tests\test_stage5_g6_foundation.py tests\test_stage5_g8_freeze.py tests\test_stage5_question_mapping.py || exit /b 15
python scripts\stage5_g5_foundation.py handoff --g6-pass --g8-pass || exit /b 16
exit /b 0
