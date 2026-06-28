@echo off
title Create Admin & Vendor Users
cd /d "%~dp0"
echo Creating database and admin/vendor users...
echo.
python init_db.py
echo.
pause
