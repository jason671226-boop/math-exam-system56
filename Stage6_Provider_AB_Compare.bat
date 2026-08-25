@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" exit /b 20
python scripts\stage6_provider_tools.py compare %~1
exit /b %ERRORLEVEL%
