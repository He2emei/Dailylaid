@echo off
chcp 65001 >nul
title Dailylaid - AI Agent

echo =======================================
echo   Dailylaid - 个人日常事务 AI Agent
echo =======================================
echo.

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [错误] 未找到虚拟环境，请先运行:
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

echo 正在启动...
echo.
.venv\Scripts\python app.py

pause
