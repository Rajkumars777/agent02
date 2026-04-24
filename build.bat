@echo off
setlocal enabledelayedexpansion
title NEXUS — Build Portable Release

echo.
echo ========================================================
echo   NEXUS Portable Release Builder
echo ========================================================
echo.

:: ── Set working directory to project root ─────────────────────────────────
cd /d "%~dp0"
set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "VENV=%BACKEND%\venv"
set "PYTHON=%VENV%\Scripts\python.exe"
set "PIP=%VENV%\Scripts\pip.exe"
set "DIST=%ROOT%dist\NEXUS"

:: ── Step 1: Check prerequisites ───────────────────────────────────────────
echo [1/6] Checking prerequisites...

:: Use bundled node if system node not found
where node >nul 2>&1
if errorlevel 1 (
    echo    System node not found — injecting bundled Node.js from bin\node\
    set "PATH=%ROOT%bin\node;%PATH%"
)

:: Verify node is available now
where node >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js not found!
    echo        Place node.exe in bin\node\ or install Node.js from https://nodejs.org
    pause
    exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
    echo    npm not in PATH — trying bundled npm...
    set "PATH=%ROOT%bin\node;%PATH%"
)

if not exist "%PYTHON%" (
    echo ERROR: venv not found at %VENV%
    echo        Please run: python -m venv backend\venv
    echo        Then:       backend\venv\Scripts\pip install -r backend\requirements.txt
    pause
    exit /b 1
)

echo    Python : %PYTHON%
echo    Root   : %ROOT%

:: ── Step 2: Install openclaw locally so it gets bundled ──────────────────
echo.
echo [2/6] Installing openclaw locally (for bundling)...

if not exist "%ROOT%node_modules\openclaw\openclaw.mjs" (
    echo    Running: npm install openclaw --save-dev
    call npm install openclaw --save-dev --prefer-offline 2>nul
    if errorlevel 1 (
        echo    WARNING: npm install openclaw failed.
        echo    Trying npm install from bin\node directory...
        "%ROOT%bin\node\npm.cmd" install openclaw --save-dev --prefix "%ROOT%" 2>nul
        if errorlevel 1 (
            echo    WARNING: Could not install openclaw locally.
            echo    NEXUS will auto-install it on first run on the target machine.
        ) else (
            echo    openclaw installed via bundled npm.
        )
    ) else (
        echo    openclaw installed successfully.
    )
) else (
    echo    openclaw already present at node_modules\openclaw\openclaw.mjs
)

:: ── Step 3: Build Next.js static export ──────────────────────────────────
echo.
echo [3/6] Building Next.js static frontend...
call npm run build
if errorlevel 1 (
    echo ERROR: npm run build failed!
    pause
    exit /b 1
)
echo    Frontend built successfully ^→ out\

:: ── Step 4: Install PyInstaller in venv ──────────────────────────────────
echo.
echo [4/6] Ensuring PyInstaller is installed...
"%PIP%" install pyinstaller --quiet
if errorlevel 1 (
    echo ERROR: PyInstaller install failed!
    pause
    exit /b 1
)
echo    PyInstaller ready.

:: ── Step 5: Run PyInstaller ───────────────────────────────────────────────
echo.
echo [5/6] Compiling NEXUS.exe (this takes 3-8 minutes)...
"%PYTHON%" -m PyInstaller nexus_launcher.spec --clean --noconfirm
if errorlevel 1 (
    echo ERROR: PyInstaller build failed!
    pause
    exit /b 1
)

:: ── Step 6: Finalize release folder ──────────────────────────────────────
echo.
echo [6/6] Finalizing release folder...

:: Write config.json (no API keys — user fills in settings)
(
echo {
echo     "ai_provider": "google",
echo     "api_key": "",
echo     "ai_model": "gemini-2.5-flash-lite",
echo     "openclaw_gateway_url": "http://localhost:18789/api/v1/message",
echo     "openclaw_channel": "",
echo     "openclaw_token": "",
echo     "openai_api_key": ""
echo }
) > "%DIST%\config.json"

:: Write README
(
echo NEXUS Agent — Portable Release
echo ================================
echo.
echo HOW TO RUN:
echo   Double-click NEXUS.exe — browser opens automatically.
echo.
echo FIRST-TIME SETUP:
echo   1. NEXUS will auto-install its gateway service on first launch.
echo      This takes 1-3 minutes and requires an internet connection.
echo      Subsequent launches are instant.
echo   2. Browser opens to http://localhost:8000
echo   3. Go to Settings ^(gear icon^) and paste your API key:
echo      - Google Gemini: free key at https://aistudio.google.com
echo      - OpenAI:        key at https://platform.openai.com
echo   4. Click Save.
echo.
echo REQUIREMENTS:
echo   - Windows 10/11
echo   - Node.js v22+ ^(download: https://nodejs.org^)
echo   - Internet connection on first launch ^(for gateway auto-install^)
echo.
echo SYSTEM TRAY:
echo   NEXUS runs in the system tray ^(bottom-right corner^).
echo   Right-click the icon to open browser or quit.
echo.
echo LOGS ^(if something goes wrong^):
echo   %%LOCALAPPDATA%%\NEXUS\nexus_launcher.log
echo   %%LOCALAPPDATA%%\NEXUS\openclaw_install.log
) > "%DIST%\README.txt"

echo.
echo ========================================================
echo   Build Complete!
echo ========================================================
echo.
echo   Output folder : %DIST%
echo.
echo   To share:
echo     1. Zip the entire dist\NEXUS\ folder
echo     2. Send the zip
echo     3. They extract it and double-click NEXUS.exe
echo.

explorer "%DIST%"
pause
