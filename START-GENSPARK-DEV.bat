@echo off
setlocal enabledelayedexpansion
title GenSpark — Local Dev (API + UI)
cd /d "%~dp0"

echo.
echo ============================================================
echo   GenSpark — Professional local stack
echo   Backend (AI + YOLO + Gemini + local DB parts): http://127.0.0.1:5000
echo   React UI (Vite):                             http://localhost:5173
echo ============================================================
echo.

REM --- Free ports 5000 and 5173 ---
for %%P in (5000 5173) do (
  for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%%P" ^| findstr "LISTENING"') do (
    echo [stop] Port %%P — PID %%a
    taskkill /PID %%a /F >nul 2>&1
  )
)
timeout /t 2 /nobreak >nul

REM --- Backend venv + deps (first run may take several minutes) ---
set "BACKEND=%~dp0backend"
set "PY=%BACKEND%\.venv\Scripts\python.exe"
set "PIP=%BACKEND%\.venv\Scripts\pip.exe"

if not exist "%PY%" (
  echo [setup] Creating backend virtual environment...
  py -3.11 -m venv "%BACKEND%\.venv"
  if errorlevel 1 (
    py -3.10 -m venv "%BACKEND%\.venv"
  )
)

if not exist "%PY%" (
  echo ERROR: Could not create backend\.venv — install Python 3.10+ from python.org
  pause
  exit /b 1
)

echo [setup] Installing backend requirements (skip if already installed)...
"%PIP%" install -q -r "%BACKEND%\requirements.txt"
if errorlevel 1 (
  echo ERROR: pip install failed. Check internet and requirements.txt
  pause
  exit /b 1
)

if not exist "%BACKEND%\best.pt" (
  echo [setup] Copying YOLO weights...
  call "%BACKEND%\copy_weights.bat"
)

if not exist "%BACKEND%\.env" (
  echo [setup] Creating backend\.env from .env.example...
  if exist "%BACKEND%\.env.example" copy /Y "%BACKEND%\.env.example" "%BACKEND%\.env" >nul
)
echo [check] Edit backend\.env — set OPENAI_API_KEY ^(ChatGPT^) and DB_PASSWORD ^(MySQL^).

echo [check] Testing local MySQL ^(genspark_erp^)...
"%PY%" "%BACKEND%\scripts\test_db_connection.py"
if errorlevel 1 (
  echo.
  echo ERROR: Cannot connect to MySQL. Start XAMPP/MySQL and fix backend\.env DB_* settings.
  echo        Must match vendor dashboard\.env ^(same DB_USER / DB_PASSWORD / DB_NAME^).
  pause
  exit /b 1
)
echo [check] Local database OK.

REM --- React deps ---
if not exist "%~dp0my-react-app\node_modules" (
  echo [setup] npm install (my-react-app)...
  pushd "%~dp0my-react-app"
  call npm install
  popd
)

echo.
echo [start] Launching Backend + Frontend in separate windows...
echo.

REM Do NOT run vendor dashboard\run.py on 5000 — Chatbot needs backend\app.py (Gemini routes).
start "GenSpark Backend :5000" cmd /k "cd /d "%BACKEND%" && chcp 65001 >nul && set PYTHONIOENCODING=utf-8 && set PYTHONUTF8=1 && set FLASK_DEBUG=0 && set PORT=5000 && "%PY%" app.py"
timeout /t 3 /nobreak >nul
start "GenSpark React UI :5173" cmd /k "cd /d "%~dp0my-react-app" && npm run dev"

echo.
echo Done. Open in browser:
echo   LOCAL:  http://localhost:5173
echo   LIVE:   https://genspark-frontend.vercel.app
echo.
echo Backend health: http://127.0.0.1:5000/health
echo DB check:        http://127.0.0.1:5000/api/db-health
echo Components page loads parts from local MySQL (products table).
echo Chatbot uses local API automatically on localhost.
echo.
pause
