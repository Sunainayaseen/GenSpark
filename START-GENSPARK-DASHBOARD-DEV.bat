@echo off
setlocal enabledelayedexpansion
title GenSpark - Dev (Flask API :5000 + React :5173)
cd /d "%~dp0"

echo ============================================================
echo   GenSpark - backend (Flask, local genspark_erp) + React UI
echo   API : http://127.0.0.1:5000   (DB-driven recommend-build, real component IDs)
echo   UI  : http://localhost:5173
echo ============================================================
echo.

REM --- Free ports 5000 and 5173 (stop whatever is already listening) ---
for %%P in (5000 5173) do (
  for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%%P" ^| findstr "LISTENING"') do (
    echo [stop] Port %%P - PID %%a
    taskkill /PID %%a /F >nul 2>&1
  )
)
timeout /t 1 /nobreak >nul

set "BACKEND=%~dp0backend"
set "FRONTEND=%~dp0frontend"
set "PY=%BACKEND%\.venv\Scripts\python.exe"

REM --- Backend venv check ---
if not exist "%PY%" (
  echo ERROR: backend\.venv not found. Create it once:
  echo     py -3.11 -m venv "%BACKEND%\.venv"
  echo     "%BACKEND%\.venv\Scripts\pip.exe" install -r "%BACKEND%\requirements.txt"
  pause
  exit /b 1
)

REM --- Quick MySQL reminder (the backend needs genspark_erp on localhost) ---
echo [check] Make sure MySQL is running and genspark_erp is seeded:
echo         "%PY%" "%BACKEND%\seed_vendors_components.py"
echo         "%PY%" "%BACKEND%\seed_prebuilt_parts.py"
echo         "%PY%" "%BACKEND%\seed_build_components.py"
echo.

echo [start] backend on :5000  (first start takes ~15s while YOLO preloads)...
start "GenSpark API :5000" cmd /k "cd /d "%BACKEND%" && set FLASK_ENV=development && set PYTHONUTF8=1 && set PYTHONIOENCODING=utf-8 && "%PY%" run.py"
timeout /t 3 /nobreak >nul

REM --- React deps (first run only) ---
if not exist "%FRONTEND%\node_modules" (
  echo [setup] npm install (frontend) - first run only...
  pushd "%FRONTEND%"
  call npm install
  popd
)

echo [start] React UI on :5173 ...
start "GenSpark React UI :5173" cmd /k "cd /d "%FRONTEND%" && npm run dev"

echo.
echo Done. Open in browser:
echo   Chatbot (one-click cart): http://localhost:5173/chatbot
echo   Prebuilt PCs            : http://localhost:5173/builds
echo   Backend health          : http://127.0.0.1:5000/health
echo.
echo Tip: enter a budget + purpose, click Get recommendations, then Add to cart.
echo.
pause
