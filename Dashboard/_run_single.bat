@echo off
REM Single Dashboard backend instance on :5000 (reloader OFF — no stacked servers).
REM Double-click this to run the chatbot backend. Leave the window open.
title GenSpark Dashboard API :5000 (single instance)
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set FLASK_ENV=development

REM --- free port 5000 first (stop any stacked/old servers) ---
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5000" ^| findstr "LISTENING"') do (
  echo [stop] old server on :5000 - PID %%a
  taskkill /PID %%a /F >nul 2>&1
)

echo [start] Dashboard backend on http://127.0.0.1:5000  (first start ~15s for YOLO)...
".venv\Scripts\python.exe" _run_single.py
echo.
echo Server stopped. Press any key to close.
pause >nul
