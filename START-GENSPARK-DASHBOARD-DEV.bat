@echo off
setlocal enabledelayedexpansion
title GenSpark - Backend Dev (DB-driven API :5000 + React :5173)
cd /d "%~dp0"

echo ============================================================
echo   GenSpark - Backend API + React UI (local genspark_erp)
echo   API : http://127.0.0.1:5000   (DB-driven recommend-build, real component IDs)
echo   UI  : http://localhost:5173
echo ------------------------------------------------------------
echo   Use THIS launcher (not START-GENSPARK-DEV.bat) for the
echo   one-click cart demo: it runs the Backend API, which
echo   serves build_components from the seeded local catalog.
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

set "DASH=%~dp0backend"
set "PY=%DASH%\.venv\Scripts\python.exe"

REM --- Backend venv check ---
if not exist "%PY%" (
  echo ERROR: backend\.venv not found. Create it once:
  echo     py -3.11 -m venv "%DASH%\.venv"
  echo     "%DASH%\.venv\Scripts\pip.exe" install -r "%DASH%\requirements.txt"
  pause
  exit /b 1
)

REM --- Quick DB reminder (first run only: seeds roles + default admin/vendor) ---
echo [check] First run only, seed the database:
echo         "%PY%" "%DASH%\init_db.py"
echo.

echo [start] Backend API on :5000  (first start takes ~15s while YOLO preloads)...
start "GenSpark Backend API :5000" cmd /k "cd /d "%DASH%" && set FLASK_ENV=development && set PYTHONUTF8=1 && set PYTHONIOENCODING=utf-8 && "%PY%" run.py"
timeout /t 3 /nobreak >nul

REM --- React deps (first run only) ---
if not exist "%~dp0frontend\node_modules" (
  echo [setup] npm install (frontend) - first run only...
  pushd "%~dp0frontend"
  call npm install
  popd
)

echo [start] React UI on :5173 ...
start "GenSpark React UI :5173" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo Done. Open in browser:
echo   Chatbot (one-click cart): http://localhost:5173/chatbot
echo   Prebuilt PCs            : http://localhost:5173/builds
echo   Backend health          : http://127.0.0.1:5000/health
echo.
echo Tip: enter a budget + purpose, click Get recommendations, then Add to cart.
echo.
pause
