@echo off
setlocal EnableDelayedExpansion
title NEXUS — Build Desktop Application
color 0A

echo.
echo  =====================================================
echo    NEXUS Agent02 ^| Build System
echo    Producing: NEXUS.exe (standalone desktop app)
echo  =====================================================
echo.

:: ── Configuration ────────────────────────────────────────────────────────────
set ROOT=%~dp0
set BACKEND=%ROOT%backend
set VENV=%BACKEND%\venv
set PIP=%VENV%\Scripts\pip.exe
set PYTHON=%VENV%\Scripts\python.exe
set DIST=%ROOT%dist

:: ── Step 1: Verify prerequisites ─────────────────────────────────────────────
echo [1/6] Checking prerequisites...

where node >nul 2>&1
if !errorlevel! neq 0 (
    echo  WARNING: Global Node.js not found. It's okay, we are downloading portable Node.js anyway.
)

where python >nul 2>&1
if !errorlevel! neq 0 (
    echo  ERROR: Python not found.
    pause & exit /b 1
)
echo  OK: Node.js and Python found.

:: ── Step 2: Install Python deps (including pyinstaller + pystray) ────────────
echo.
echo [2/6] Setting up Python environment...

if not exist "%VENV%" (
    echo  Creating virtualenv...
    python -m venv "%VENV%"
)

echo  Installing/updating Python packages...
"%PIP%" install -r "%BACKEND%\requirements.txt" -q
"%PIP%" install pyinstaller pystray Pillow -q
echo  Python dependencies ready.

:: ── Step 3: Build Next.js static export ──────────────────────────────────────
echo.
echo [3/6] Building Next.js frontend (static export)...

if not exist "%ROOT%node_modules" (
    echo  Running npm install...
    npm install --prefer-offline
)

call npm run build
if !errorlevel! neq 0 (
    echo  ERROR: Next.js build failed. Check the output above.
    pause & exit /b 1
)

if not exist "%ROOT%out\index.html" (
    echo  ERROR: out\index.html not found after build.
    echo  Make sure next.config.js has: output: 'export'
    pause & exit /b 1
)
echo  Frontend built: out\ folder ready.

:: ── Step 4: Copy frontend API base to use port 8000 in production ────────────
echo.
echo [4/6] Patching production API base URL...
:: The static build already hardcodes http://127.0.0.1:8000 — no patch needed.
echo  API base: http://127.0.0.1:8000 (backend serves both API and frontend)

:: ── Step 4.5: Download Portable Node.js ─────────────────────────────────────
echo.
echo [4.5/6] Downloading portable Node.js...
if not exist "%ROOT%bin\node\node.exe" (
    mkdir "%ROOT%bin" 2>nul
    echo  Downloading Node.js v22.14.0 ... this may take a minute...
    powershell -Command "Invoke-WebRequest -Uri 'https://nodejs.org/dist/v22.14.0/node-v22.14.0-win-x64.zip' -OutFile '%ROOT%bin\node.zip'"
    echo  Extracting Node.js...
    powershell -Command "Expand-Archive -Path '%ROOT%bin\node.zip' -DestinationPath '%ROOT%bin\temp_node' -Force"
    move /Y "%ROOT%bin\temp_node\node-v22.14.0-win-x64" "%ROOT%bin\node" >nul
    rmdir /S /Q "%ROOT%bin\temp_node"
    del /f /q "%ROOT%bin\node.zip"
    echo  Portable Node.js successfully extracted to bin\node.
) else (
    echo  Portable Node.js already exists in bin\node. Skipping download.
)

:: ── Step 5: Run PyInstaller ───────────────────────────────────────────────────
echo.
echo [5/6] Packaging with PyInstaller...

if exist "%DIST%\NEXUS.exe" del /f /q "%DIST%\NEXUS.exe"
if exist "%ROOT%build" rmdir /s /q "%ROOT%build" 2>nul

"%PYTHON%" -m PyInstaller "%ROOT%NEXUS.spec" --distpath "%DIST%" --workpath "%ROOT%build" --noconfirm

if !errorlevel! neq 0 (
    echo  ERROR: PyInstaller failed. Check the output above.
    pause & exit /b 1
)

if not exist "%DIST%\NEXUS.exe" (
    echo  ERROR: NEXUS.exe not found after PyInstaller run.
    pause & exit /b 1
)

:: ── Step 6: Done ─────────────────────────────────────────────────────────────
echo.
echo [6/6] Build complete!

for %%F in ("%DIST%\NEXUS.exe") do set SIZE=%%~zF
set /a SIZE_MB=!SIZE! / 1048576

echo.
echo  =====================================================
echo    SUCCESS!
echo    Output: dist\NEXUS.exe  (!SIZE_MB! MB)
echo.
echo    Share dist\NEXUS.exe with anyone.
echo    On first run it will:
echo      - Download portable Node.js (~30 MB, once)
echo      - Install OpenClaw automatically
echo      - Ask for their API key
echo      - Open the app in their browser
echo  =====================================================
echo.

:: Open the dist folder
explorer "%DIST%"

pause
