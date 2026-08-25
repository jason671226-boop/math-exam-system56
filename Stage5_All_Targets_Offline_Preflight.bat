@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

for /f "delims=" %%B in ('git branch --show-current') do set "PILOT_BRANCH=%%B"
if /I not "%PILOT_BRANCH%"=="stage5/generic-grade-engine" exit /b 20

set "PREFLIGHT_FAILED=0"
for %%G in (G1 G2 G3 G4 G7 G9 G10_GENERAL G11_A G11_B G12_A G12_B) do (
  python scripts\stage5_grade_foundation.py --grade %%G preflight
  if errorlevel 1 set "PREFLIGHT_FAILED=1"
)
python scripts\stage5_grade_foundation.py --grade G7 resume-queue
if errorlevel 1 set "PREFLIGHT_FAILED=1"
exit /b !PREFLIGHT_FAILED!
