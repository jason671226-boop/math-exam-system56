@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
title MathAI v0.8.5 Private Beta 一鍵安裝

set "APPDIR=C:\MathAI\app"
set "VENV_PY=C:\MathAI\.venv\Scripts\python.exe"
set "PATCHDIR=%~dp0"
set "PORT=8501"

echo.
echo ============================================================
echo   MathAI v0.8.5 Private Beta 一鍵安裝
echo ============================================================
echo.

if not exist "%APPDIR%\app.py" (
    echo [ERROR] 找不到 %APPDIR%\app.py
    goto :FAIL
)
if not exist "%PATCHDIR%app.py" (
    echo [ERROR] 修正包內找不到 app.py
    goto :FAIL
)
if not exist "%PATCHDIR%diagnostic_pilot_ui.py" (
    echo [ERROR] 修正包內找不到 diagnostic_pilot_ui.py
    goto :FAIL
)

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "TS=%%i"
set "BACKUPDIR=%APPDIR%\backup\PrivateBeta_%TS%"

echo [1/7] 建立備份：%BACKUPDIR%
mkdir "%BACKUPDIR%" >nul 2>&1
if errorlevel 1 goto :FAIL

copy /y "%APPDIR%\app.py" "%BACKUPDIR%\app.py" >nul
if exist "%APPDIR%\diagnostic_pilot_ui.py" (
    copy /y "%APPDIR%\diagnostic_pilot_ui.py" "%BACKUPDIR%\diagnostic_pilot_ui.py" >nul
)

echo [2/7] 停止 localhost:%PORT% 的舊 Streamlit...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$c=Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue; if($c){$ids=$c.OwningProcess | Select-Object -Unique; foreach($pid2 in $ids){try{Stop-Process -Id $pid2 -Force -ErrorAction Stop}catch{}}}" >nul 2>&1

echo [3/7] 安裝新版程式...
copy /y "%PATCHDIR%app.py" "%APPDIR%\app.py" >nul
if errorlevel 1 goto :ROLLBACK
copy /y "%PATCHDIR%diagnostic_pilot_ui.py" "%APPDIR%\diagnostic_pilot_ui.py" >nul
if errorlevel 1 goto :ROLLBACK

if exist "%VENV_PY%" (
    set "PYTHON=%VENV_PY%"
) else (
    set "PYTHON=python"
)

echo [4/7] 執行 Python 語法檢查...
"%PYTHON%" -m py_compile "%APPDIR%\app.py" "%APPDIR%\diagnostic_pilot_ui.py"
if errorlevel 1 goto :ROLLBACK

echo [5/7] 驗證 APP_VERSION=v0.8.5...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$t=Get-Content -Raw -Encoding UTF8 '%APPDIR%\app.py'; if($t -match 'APP_VERSION\s*=\s*\"v0\.8\.5\"'){exit 0}else{exit 1}"
if errorlevel 1 goto :ROLLBACK

echo [6/7] 啟動 MathAI...
start "MathAI v0.8.5" cmd /k ""%PYTHON%" -m streamlit run "%APPDIR%\app.py""

echo [7/7] 開啟瀏覽器...
timeout /t 3 /nobreak >nul
start "" "http://localhost:%PORT%"

echo.
echo ============================================================
echo   安裝完成
echo ============================================================
echo   備份位置：
echo   %BACKUPDIR%
echo.
echo   請確認：
echo   - 左側版本 v0.8.5
echo   - 立即試用 30 點
echo   - 新會員提示 200 點
echo.
echo   Supabase SQL 尚未自動執行，避免誤動正式資料庫。
echo ============================================================
echo.
pause
exit /b 0

:ROLLBACK
echo.
echo [ERROR] 安裝或檢查失敗，正在自動還原...
if exist "%BACKUPDIR%\app.py" copy /y "%BACKUPDIR%\app.py" "%APPDIR%\app.py" >nul
if exist "%BACKUPDIR%\diagnostic_pilot_ui.py" copy /y "%BACKUPDIR%\diagnostic_pilot_ui.py" "%APPDIR%\diagnostic_pilot_ui.py" >nul
echo 已還原原始檔案。
goto :FAIL

:FAIL
echo.
echo [FAILED] 此次更新未完成。
echo 請把這個黑色視窗截圖傳給 ChatGPT。
echo.
pause
exit /b 1
