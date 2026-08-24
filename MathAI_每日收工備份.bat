@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo MathAI - Daily End-of-Work Backup
echo GitHub version + OneDrive ZIP protection
echo Production database is NOT modified by this tool.
echo ============================================================

set "TARGET="
if defined OneDrive if exist "%OneDrive%" set "TARGET=%OneDrive%\MathAI_Backups"
if not defined TARGET if defined OneDriveConsumer if exist "%OneDriveConsumer%" set "TARGET=%OneDriveConsumer%\MathAI_Backups"

if defined TARGET (
  echo Cloud target: %TARGET%
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\mathai_daily_backup.ps1" -MaxBackups 14 -BackupTarget "%TARGET%"
) else (
  echo OneDrive desktop path not detected. Using script fallback target.
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\mathai_daily_backup.ps1" -MaxBackups 14
)
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
