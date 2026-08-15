@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
title MathAI 更新正式網站 v0.7.0

set "LOG=C:\MathAI\更新網站紀錄.txt"

> "%LOG%" echo ==========================================
>> "%LOG%" echo MathAI 更新正式網站 v0.7.0
>> "%LOG%" echo 開始時間：%date% %time%
>> "%LOG%" echo ==========================================

call :MAIN >> "%LOG%" 2>&1
set "RESULT=%ERRORLEVEL%"

echo.
echo ==========================================
if "%RESULT%"=="0" (
    echo 更新流程已完成。
) else (
    echo 更新失敗，錯誤碼：%RESULT%
)
echo ==========================================
echo.
echo 完整紀錄：
echo %LOG%
echo.
type "%LOG%"
echo.
pause
exit /b %RESULT%


:MAIN
set "SOURCE=C:\MathAI\app"
set "REPO=C:\Users\ASUS\Documents\GitHub\math-exam-system56"
set "SITE=https://math-exam-system56-jasonlin.streamlit.app"

echo 來源：%SOURCE%
echo GitHub 專案：%REPO%
echo.

if not exist "%SOURCE%\app.py" (
    echo [錯誤] 找不到 %SOURCE%\app.py
    exit /b 10
)

if not exist "%REPO%\.git" (
    echo [錯誤] 找不到 GitHub 專案：%REPO%
    exit /b 11
)

set "GIT="
for /f "delims=" %%G in ('where git.exe 2^>nul') do (
    if not defined GIT set "GIT=%%G"
)

if not defined GIT (
    for /f "delims=" %%G in ('dir /b /s "%LOCALAPPDATA%\GitHubDesktop\git.exe" 2^>nul') do (
        if not defined GIT set "GIT=%%G"
    )
)

if not defined GIT (
    echo [錯誤] 找不到 git.exe，請先開啟 GitHub Desktop。
    exit /b 12
)

echo Git：%GIT%

set "BRANCH="
for /f "delims=" %%B in ('cmd /c ""%GIT%" -C "%REPO%" branch --show-current"') do (
    if not defined BRANCH set "BRANCH=%%B"
)
if not defined BRANCH set "BRANCH=main"

echo 分支：%BRANCH%
echo.

echo [1/4] 複製最新檔案
for %%F in (app.py ai_service.py requirements.txt learning_map.py curriculum_map.json line_pay_qr.jpg) do (
    if exist "%SOURCE%\%%F" (
        copy /Y "%SOURCE%\%%F" "%REPO%\%%F" >nul
        echo 已複製 %%F
    ) else (
        echo 略過 %%F
    )
)

echo.
echo [2/4] 加入 Git 變更
"%GIT%" -C "%REPO%" add app.py ai_service.py requirements.txt learning_map.py curriculum_map.json line_pay_qr.jpg
if errorlevel 1 exit /b 20

"%GIT%" -C "%REPO%" diff --cached --quiet
if not errorlevel 1 (
    echo [提醒] 沒有新變更可上傳。
    echo 請確認 C:\MathAI\app 左側顯示版本 v0.7.0。
    start "" "%SITE%"
    exit /b 0
)

echo.
echo [3/4] 建立 Commit
"%GIT%" -C "%REPO%" commit -m "MathAI data architecture v0.7.0"
if errorlevel 1 exit /b 21

echo.
echo [4/4] Push 到 GitHub
"%GIT%" -C "%REPO%" push origin "%BRANCH%"
if errorlevel 1 exit /b 22

echo.
echo [成功] 已上傳 GitHub。
echo 等 Streamlit Cloud 部署後，請按 Ctrl+F5。
echo 雲端左側顯示 v0.7.0 才代表成功。
start "" "%SITE%"
exit /b 0
