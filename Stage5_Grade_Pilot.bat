@echo off
setlocal
cd /d "%~dp0"

if "%~1"=="" exit /b 20
echo %~1| findstr /R /I "^G[1-9]$ ^G1[0-2]$" >nul || exit /b 21
for /f "delims=" %%B in ('git branch --show-current') do set "PILOT_BRANCH=%%B"
if /I not "%PILOT_BRANCH%"=="stage5/generic-grade-engine" exit /b 22

python scripts\stage5_grade_foundation.py --grade %~1 all --regression-pass
exit /b %ERRORLEVEL%
