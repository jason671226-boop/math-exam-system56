@echo off
setlocal
cd /d "%~dp0"

if "%~1"=="" exit /b 20
echo %~1| findstr /R /I "^G[1-4]$ ^G7$ ^G9$ ^G10_GENERAL$ ^G11_A$ ^G11_B$ ^G12_A$ ^G12_B$" >nul || exit /b 21
for /f "delims=" %%B in ('git branch --show-current') do set "PILOT_BRANCH=%%B"
if /I not "%PILOT_BRANCH%"=="stage5/generic-grade-engine" exit /b 22

set "RESUME_COMMAND=holdout-first"
if /I "%~2"=="--full" set "RESUME_COMMAND=full-validation"
if /I "%~2"=="--fallback" set "RESUME_COMMAND=fallback"
if not "%~2"=="" if /I not "%~2"=="--full" if /I not "%~2"=="--fallback" exit /b 23

python scripts\stage5_grade_foundation.py --grade %~1 %RESUME_COMMAND% || exit /b %ERRORLEVEL%
set "TMP=%CD%\.local\pytest_tmp_%~1_%RANDOM%_%RANDOM%"
set "TEMP=%TMP%"
if not exist "%TMP%" mkdir "%TMP%" || exit /b 29
python -m pytest -q --basetemp "%TMP%" tests\test_stage5_grade_engine.py tests\test_stage5_g5_foundation.py tests\test_stage5_g6_foundation.py tests\test_stage5_g8_freeze.py tests\test_stage5_question_mapping.py || exit /b 30
python scripts\stage5_grade_foundation.py --grade %~1 handoff --regression-pass
exit /b %ERRORLEVEL%
