@echo off
setlocal
cd /d "%~dp0"

for /f "delims=" %%B in ('git branch --show-current') do set "PILOT_BRANCH=%%B"
if /I not "%PILOT_BRANCH%"=="stage5/generic-grade-engine" exit /b 20

python scripts\stage5_grade_foundation.py --grade G7 quota-probe
exit /b %ERRORLEVEL%
