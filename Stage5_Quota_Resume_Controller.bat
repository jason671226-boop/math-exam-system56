@echo off
setlocal
cd /d "%~dp0"

if "%~1"=="" exit /b 20
echo %~1| findstr /R /I "^G[1-4]$ ^G7$ ^G9$ ^G10_GENERAL$ ^G11_A$ ^G11_B$ ^G12_A$ ^G12_B$" >nul || exit /b 21
for /f "delims=" %%B in ('git branch --show-current') do set "PILOT_BRANCH=%%B"
if /I not "%PILOT_BRANCH%"=="stage5/generic-grade-engine" exit /b 22

if /I not "%~1"=="G7" (
  findstr /C:"SAFE TO PAUSE" ".local\stage5_g7_mapping_pilot\handoff_summary.json" >nul 2>nul || exit /b 24
)

call Stage5_Resume_Target.bat %*
exit /b %ERRORLEVEL%
