@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo MathAI - Backup Capacity Audit
echo READ ONLY - no ZIP / no DB write / no Git write
echo ============================================================

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\mathai_daily_backup.ps1" -AuditOnly
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo Audit completed. Please send the final screen to ChatGPT.
) else (
  echo Audit FAILED. No project or Production data was modified.
)
echo.
pause
exit /b %RC%
