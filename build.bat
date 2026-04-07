@echo off
setlocal EnableDelayedExpansion
title NEXUS — Build Desktop Application
color 0A

echo.
echo  =====================================================
echo    NEXUS Agent02 ^| Build System v3
echo    Output: dist\NEXUS\  (onedir — fast startup)
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
echo [1/7] Checking prerequisites...

where python >nul 2>&1
if !errorlevel! neq 0 (
    echo  ERROR: Python not found. Install Python 3.11+ and add to PATH.
    pause & exit /b 1
)
python --version
echo  OK: Python found.

:: ── Step 2: Python virtual environment ────────────────────────────────────────
echo.
echo [2/7] Setting up Python environment...

if not exist "%VENV%" (
    echo  Creating virtual environment...
    python -m venv "%VENV%"
)

echo  Installing/updating Python packages...
"%PIP%" install -q --upgrade pip
"%PIP%" install -q -r "%BACKEND%\requirements.txt"
"%PIP%" install -q pyinstaller pystray Pillow
echo  Python dependencies ready.

:: ── Step 3: Build Next.js static export ──────────────────────────────────────
echo.
echo [3/7] Building Next.js frontend (static export)...

if not exist "%ROOT%node_modules" (
    echo  Running npm install...
    npm install --prefer-offline
)

:: Ensure favicon.ico is in src/app/ for App Router (prevents build error)
if not exist "%ROOT%src\app\favicon.ico" (
    echo  Copying favicon.ico to src\app/ - App Router fix...
    copy /Y "%ROOT%public\favicon.ico" "%ROOT%src\app\favicon.ico" >nul
)

:: Clean stale output — guarantees the fresh UI is packed into the EXE
echo  Cleaning stale .next\ and out\ directories...
if exist "%ROOT%.next" rmdir /s /q "%ROOT%.next" 2>nul
if exist "%ROOT%out"   rmdir /s /q "%ROOT%out"   2>nul

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
echo  Frontend built successfully: out\ folder ready.

:: ── Step 4: Write version stamp into out/ ────────────────────────────────────
echo.
echo [4/7] Writing version stamp...
for /f "tokens=*" %%T in ('powershell -NoProfile -Command "[int][double]::Parse((Get-Date -UFormat %%s))"') do set BUILD_TS=%%T
echo %BUILD_TS%> "%ROOT%out\.nexus_version"
echo  Version stamp: %BUILD_TS% written to out\.nexus_version

:: ── Step 5: Download Portable Node.js ─────────────────────────────────────────
echo.
echo [5/7] Ensuring portable Node.js is ready...
if not exist "%ROOT%bin\node\node.exe" (
    mkdir "%ROOT%bin" 2>nul
    echo  Downloading Node.js v22.14.0... (one-time, ~35 MB)
    powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://nodejs.org/dist/v22.14.0/node-v22.14.0-win-x64.zip' -OutFile '%ROOT%bin\node.zip'"
    echo  Extracting Node.js...
    powershell -NoProfile -Command "Expand-Archive -Path '%ROOT%bin\node.zip' -DestinationPath '%ROOT%bin\temp_node' -Force"
    move /Y "%ROOT%bin\temp_node\node-v22.14.0-win-x64" "%ROOT%bin\node" >nul
    rmdir /S /Q "%ROOT%bin\temp_node" 2>nul
    del  /f /q  "%ROOT%bin\node.zip"  2>nul
    echo  Portable Node.js extracted to bin\node.
) else (
    echo  Portable Node.js already in bin\node — skipping.
)

:: ── Step 6: Run PyInstaller (onedir for fast startup) ─────────────────────────
echo.
echo [6/7] Packaging with PyInstaller (onedir mode — no UPX)...

:: Clean old build artifacts
if exist "%DIST%\NEXUS"  rmdir /s /q "%DIST%\NEXUS"  2>nul
if exist "%ROOT%build"   rmdir /s /q "%ROOT%build"   2>nul

"%PYTHON%" -m PyInstaller "%ROOT%NEXUS.spec" --distpath "%DIST%" --workpath "%ROOT%build" --noconfirm --clean

if !errorlevel! neq 0 (
    echo  ERROR: PyInstaller failed. Check the output above.
    pause & exit /b 1
)

if not exist "%DIST%\NEXUS\NEXUS.exe" (
    echo  ERROR: NEXUS.exe not found in dist\NEXUS\ after PyInstaller run.
    pause & exit /b 1
)

:: ── Step 7: Create distributable ZIP ──────────────────────────────────────────
echo.
echo [7/7] Creating distributable ZIP...
set ZIP_NAME=NEXUS-Desktop-%BUILD_TS%.zip
powershell -NoProfile -Command "Compress-Archive -Path '%DIST%\NEXUS\*' -DestinationPath '%DIST%\%ZIP_NAME%' -Force"
echo  Created: dist\%ZIP_NAME%

:: Calculate folder size
for /f "tokens=*" %%S in ('powershell -NoProfile -Command "(Get-ChildItem -Path '%DIST%\NEXUS' -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB | [math]::Round(1)"') do set SIZE_MB=%%S

echo.
echo  =====================================================
echo    SUCCESS!
echo    EXE:  dist\NEXUS\NEXUS.exe
echo    ZIP:  dist\%ZIP_NAME%
echo    Size: ~!SIZE_MB! MB (uncompressed folder)
echo.
echo    How to distribute:
echo      Option A: Share the entire dist\NEXUS\ folder
echo      Option B: Share the ZIP file (self-contained)
echo.
echo    On first run:
echo      - Downloads portable Node.js (~35 MB, once only)
echo      - Auto-installs OpenClaw
echo      - Opens the app immediately (~2-3 sec boot)
echo  =====================================================
echo.

:: Open the dist folder
:: explorer "%DIST%"
:: pause
