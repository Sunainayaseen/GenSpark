@echo off
title Kill processes on port 5000
cd /d "%~dp0"
echo Stopping all processes using port 5000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5000" ^| findstr "LISTENING"') do (
    echo Killing PID %%a
    taskkill /PID %%a /F 2>nul
)
echo Done. Ab GenSpark chalao: python run.py  ya START-GENSPARK.bat
pause
