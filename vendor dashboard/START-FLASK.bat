@echo off
title Flask - Vendor Dashboard (Port 5000)
cd /d "%~dp0"

echo ========================================
echo  GenSpark Flask - Port 5000
echo ========================================
echo.
echo Step 1: If browser shows "invalid response", run KILL-PORT-5000.bat first.
echo Step 2: Run this file ONLY ONCE (one Flask window).
echo Step 3: Open in browser:
echo         http://127.0.0.1:5000
echo         http://127.0.0.1:5000/health
echo         http://127.0.0.1:5000/api/health
echo.
echo (To test without DB: python run_simple.py)
echo.

python run.py
pause
