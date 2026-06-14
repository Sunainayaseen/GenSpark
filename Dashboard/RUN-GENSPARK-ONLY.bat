@echo off
title GenSpark - Port free karke start
cd /d "%~dp0"

echo [1/2] Port 5000 pe jo bhi chal raha hai (CRUD app) band kar raha hoon...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"
timeout /t 2 /nobreak >nul
echo Port 5000 free. Ab GenSpark hi start hoga.

echo.
echo [2/2] GenSpark start ho raha hai...
echo Folder: %~dp0
echo.
echo Browser me kholo: http://127.0.0.1:5000
echo.
python "%~dp0run.py"
if errorlevel 1 (
    echo.
    echo Error aaya. Check: Python install hai? requirements: pip install -r requirements.txt
)
pause
