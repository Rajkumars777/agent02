@echo off
title OpenClaw Agent Launcher
echo ===================================================
echo     Starting OpenClaw Agent and UI...
echo ===================================================
echo.

echo [1/2] Starting OpenClaw Gateway Service in a new window...
start "OpenClaw Gateway" cmd /k "openclaw gateway run"

echo Waiting for OpenClaw to initialize...
timeout /t 5 /nobreak >nul

echo [2/2] Starting Next.js UI...
echo Please open http://localhost:3000 in your browser if it doesn't open automatically.
echo.
npm run dev

pause
