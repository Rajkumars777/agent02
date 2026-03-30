@echo off
setlocal EnableDelayedExpansion
title NEXUS Agent02 — Launcher
color 0A

echo.
echo  ================================================
echo    NEXUS Agent02 ^| Starting All Services...
echo  ================================================
echo.

:: ── Check if setup has been run ──────────────────────────────────────────────
if not exist "backend\config.json" (
    echo  [WARN] backend\config.json not found.
    echo  Please run setup first:  python setup.py
    pause
    exit /b 1
)

if not exist ".env.local" (
    echo  [WARN] .env.local not found. Running setup...
    python setup.py
    if !errorlevel! neq 0 (
        echo  Setup failed. Exiting.
        pause
        exit /b 1
    )
)

:: ── Check OpenClaw is installed ───────────────────────────────────────────────
where openclaw >nul 2>&1
if !errorlevel! neq 0 (
    echo  [INFO] OpenClaw not found. Running setup...
    python setup.py
    if !errorlevel! neq 0 (
        echo  Setup failed. Exiting.
        pause
        exit /b 1
    )
)

:: ── Check node_modules ────────────────────────────────────────────────────────
if not exist "node_modules" (
    echo  [INFO] node_modules not found. Running npm install...
    npm install --prefer-offline
)

:: ── Check Python venv ─────────────────────────────────────────────────────────
if not exist "backend\venv" (
    echo  [INFO] Python venv not found. Creating...
    python -m venv backend\venv
    backend\venv\Scripts\pip install -r backend\requirements.txt --quiet
)

echo.
echo  Starting services in separate windows...
echo.

:: ── 1. OpenClaw Gateway ──────────────────────────────────────────────────────
echo  [1/3] Starting OpenClaw Gateway (port 18789)...
start "OpenClaw Gateway" cmd /k "color 0B && title OpenClaw Gateway && openclaw gateway run"
timeout /t 3 /nobreak >nul

:: ── 2. Python Backend ────────────────────────────────────────────────────────
echo  [2/3] Starting Python Backend (port 8000)...
start "NEXUS Backend" cmd /k "color 0E && title NEXUS Backend && cd backend && venv\Scripts\python main.py"
timeout /t 3 /nobreak >nul

:: ── 3. Next.js Frontend ──────────────────────────────────────────────────────
echo  [3/3] Starting Next.js Frontend (port 3000)...
start "NEXUS Frontend" cmd /k "color 0D && title NEXUS Frontend && npm run dev"
timeout /t 5 /nobreak >nul

:: ── Open browser ─────────────────────────────────────────────────────────────
echo.
echo  Opening browser at http://localhost:3000 ...
start "" "http://localhost:3000"

echo.
echo  ================================================
echo    All services running! Close windows to stop.
echo  ================================================
echo.
pause
