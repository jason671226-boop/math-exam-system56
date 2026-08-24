@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo MathAI - Daily End-of-Work Backup
echo GitHub version + local/cloud ZIP protection

echo Production database is NOT modified by this tool.
echo ============================================================

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\mathai_daily_backup.ps1" -MaxBackups 14
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo Backup command completed. Check for BACKUP PASS above.
) else (
  echo Backup FAILED or BLOCKED. No Production DB data was modified.
)
echo.
pause
exit /b %RC%
