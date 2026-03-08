@echo off
REM 학원 PC Windows 시작 프로그램 등록 스크립트
REM 관리자 권한으로 실행

SET SCRIPT_DIR=%~dp0
SET STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
SET BATCH=%STARTUP%\remote-print-agent.bat

echo @echo off > "%BATCH%"
echo cd /d "%SCRIPT_DIR%" >> "%BATCH%"
echo pythonw executor\executor.py >> "%BATCH%"

echo [완료] 시작 프로그램 등록: %BATCH%
pause
