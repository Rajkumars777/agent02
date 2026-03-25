# Master build script — produces a standalone NSIS installer
# Run from the project root: .\installer_tools\build_all.ps1
# turbo-all

param(
    [string]$ProjectRoot = (Split-Path $PSScriptRoot -Parent)
)

Set-Location $ProjectRoot
$ErrorActionPreference = "Stop"

function Step($msg) {
    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
}

# ── Step 1: Build Next.js static export ──────────────────────────────────────
Step "1/3  Building Next.js static export..."
npm run build
if ($LASTEXITCODE -ne 0) { Write-Error "Next.js build failed"; exit 1 }
Write-Host "  ✓ Next.js export produced in ./out" -ForegroundColor Green

# ── Step 2: Compile Python backend → backend.exe ──────────────────────────────
Step "2/3  Compiling Python backend with PyInstaller..."
& "$PSScriptRoot\build_backend.ps1" -ProjectRoot $ProjectRoot
if ($LASTEXITCODE -ne 0) { Write-Error "Backend build failed"; exit 1 }
Write-Host "  ✓ backend.exe ready at project root" -ForegroundColor Green

# ── Step 3: Package with electron-builder → NSIS installer ────────────────────
Step "3/3  Packaging with electron-builder..."
npx electron-builder --win --publish never
if ($LASTEXITCODE -ne 0) { Write-Error "electron-builder failed"; exit 1 }

Step "BUILD COMPLETE"
$setup = Get-ChildItem "$ProjectRoot\dist\*.exe" | Select-Object -First 1
if ($setup) {
    Write-Host "  Installer: $($setup.FullName)" -ForegroundColor Green
    Write-Host "  Size:      $([math]::Round($setup.Length / 1MB, 1)) MB" -ForegroundColor Green
} else {
    Write-Warning "Could not locate installer in dist/"
}
