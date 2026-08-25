@echo off
setlocal
cd /d "%~dp0"
if /I "%~1"=="gemini" goto run
if /I "%~1"=="deepseek" goto run
exit /b 20
:run
python scripts\stage6_provider_tools.py probe %~1
exit /b %ERRORLEVEL%
