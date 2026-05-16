@echo off
setlocal enabledelayedexpansion
title GenSpark - Flask (port 5000)
cd /d "%~dp0"

echo.
echo ========================================
echo   GenSpark - port 5000 par chalega
echo ========================================
echo.

REM Check if port 5000 is already in use (PID is last column in netstat -ano)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5000 ^| findstr LISTENING') do (
    set "PID=%%a"
    goto :found
)
goto :start

:found
echo [WARNING] Port 5000 pe koi aur app chal rahi hai (PID: !PID!)
echo           Isi wajah se 127.0.0.1:5000 par GenSpark nahi dikh raha.
echo.
echo Ab do options:
echo   1) Neeche "y" likh kar Enter dabao - ye process band ho jayegi, phir GenSpark start hoga.
echo   2) Khud se wo doosri app band karo (e.g. Students CRUD), phir is window me kuch bhi likh kar Enter dabao.
echo.
set /p choice="Port 5000 free karna hai? Process band karein? (y / n): "
if /i "!choice!"=="y" (
    taskkill /PID !PID! /F 2>nul
    if errorlevel 1 (
        echo Process band nahi ho payi. Run as Administrator try karo ya manually wo app band karo.
        pause
        exit /b 1
    )
    echo Port 5000 free ho gaya. GenSpark start ho raha hai...
    timeout /t 2 /nobreak >nul
) else (
    echo Pehle doosri app band karo, phir is batch file ko dubara run karo.
    pause
    exit /b 0
)

:start
echo.
echo GenSpark Flask start ho raha hai...
echo Browser me open karo: http://127.0.0.1:5000
echo   - Admin:  http://127.0.0.1:5000/admin/dashboard
echo   - Vendor: http://127.0.0.1:5000/vendor/dashboard
echo.
python run.py
pause
