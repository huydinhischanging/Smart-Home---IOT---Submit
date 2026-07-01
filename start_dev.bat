@echo off
setlocal EnableExtensions

set "ROOT_DIR=%~dp0"
set "BACKEND_DIR=%ROOT_DIR%backend"
set "FRONTEND_DIR=%ROOT_DIR%frontend"

echo ==================================================
echo  IOT Smart Home - Dev Launcher
echo  Backend  : http://127.0.0.1:5000
echo  Frontend : http://127.0.0.1:5173
echo ==================================================
echo.

REM ── Check backend .env ──────────────────────────────────────
if not exist "%BACKEND_DIR%\.env" (
  echo [ERROR] backend\.env not found.
  echo         Copy backend\.env.example to backend\.env and fill in the values.
  pause
  exit /b 1
)
echo [OK] .env found.

REM ── Check Python ────────────────────────────────────────────
where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found in PATH.
  pause
  exit /b 1
)
echo [OK] Python found.

REM ── Check npm ───────────────────────────────────────────────
where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] npm not found in PATH. Please install Node.js first.
  pause
  exit /b 1
)
echo [OK] npm found.

REM ── npm install neu chua co node_modules ────────────────────
if not exist "%FRONTEND_DIR%\node_modules" (
  echo [INFO] Running npm install for frontend...
  pushd "%FRONTEND_DIR%"
  call npm install
  popd
  if errorlevel 1 (
    echo [ERROR] npm install failed.
    pause
    exit /b 1
  )
)
echo [OK] node_modules ready.

REM ── Launch Backend ──────────────────────────────────────────
echo.
echo [1/2] Starting Backend Flask...
start "Backend - Flask :5000" /d "%BACKEND_DIR%" cmd /k "python run.py"

REM ── Wait for port 5000 to be ready (max 60s) ────────────────
echo [INFO] Waiting for backend on port 5000...
set WAIT=0
:waitloop
netstat -ano | findstr ":5000 " | findstr "LISTENING" >nul 2>nul
if not errorlevel 1 goto backend_ready
set /a WAIT+=1
if %WAIT% geq 60 (
  echo [ERROR] Backend did not start after 60 seconds. Check the Backend window.
  pause
  exit /b 1
)
timeout /t 1 >nul
<nul set /p="."
goto waitloop

:backend_ready
echo.
echo [OK] Backend is up on port 5000.

REM ── Launch Frontend ─────────────────────────────────────────
echo [2/2] Starting Frontend Vite...
start "Frontend - Vite :5173" /d "%FRONTEND_DIR%" cmd /k "npm run dev"

echo.
echo ==================================================
echo  DONE! Both windows are now open.
echo  Backend  : http://127.0.0.1:5000
echo  Frontend : http://127.0.0.1:5173
echo  Press any key to close this window.
echo ==================================================
echo.
pause
exit /b 0
