@echo off
title Check Flask app
cd /d "%~dp0"
echo Checking if Flask app loads and routes work...
python check_app.py
echo.
pause
