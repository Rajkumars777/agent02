# Build backend Python → backend.exe using PyInstaller
# Run from the project root: .\installer_tools\build_backend.ps1

param(
    [string]$ProjectRoot = (Split-Path $PSScriptRoot -Parent)
)

$backendDir = Join-Path $ProjectRoot "backend"
$distDir    = Join-Path $ProjectRoot "dist_backend"
$outputExe  = Join-Path $ProjectRoot "backend.exe"

Write-Host "=== Building Python backend with PyInstaller ===" -ForegroundColor Cyan

# Activate the backend venv if it exists
$venvPython = Join-Path $backendDir "venv\Scripts\python.exe"
if (-Not (Test-Path $venvPython)) {
    Write-Error "Cannot find $venvPython - please create a venv inside backend/ first."
    exit 1
}

# Ensure all dependencies from requirements.txt are installed
Write-Host "Checking/Installing requirements.txt..." -ForegroundColor Yellow
& $venvPython -m pip install -r (Join-Path $backendDir "requirements.txt") --quiet

# Ensure PyInstaller is installed
& $venvPython -m pip install pyinstaller --quiet

Write-Host "Running PyInstaller..." -ForegroundColor Yellow

& $venvPython -m PyInstaller `
    --onefile `
    --noconsole `
    --name "backend" `
    --distpath $distDir `
    --workpath "$env:TEMP\PyInstaller_build" `
    --specpath "$env:TEMP\PyInstaller_spec" `
    --add-data "$backendDir\api;api" `
    --add-data "$backendDir\core;core" `
    --add-data "$backendDir\capabilities;capabilities" `
    --collect-all "openai" `
    --collect-all "httpx" `
    --collect-all "httpcore" `
    --collect-all "websocket" `
    --collect-all "yfinance" `
    --collect-all "cryptography" `
    --collect-all "pyautogui" `
    --collect-all "psutil" `
    --collect-all "appopener" `
    (Join-Path $backendDir "main.py")

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

# Move backend.exe to project root so electron-builder can pick it up
$builtExe = Join-Path $distDir "backend.exe"
if (Test-Path $builtExe) {
    Copy-Item $builtExe $outputExe -Force
    Write-Host "backend.exe copied to: $outputExe" -ForegroundColor Green
} else {
    Write-Error "PyInstaller did not produce $builtExe"
    exit 1
}

Write-Host "=== Backend build complete ===" -ForegroundColor Green
