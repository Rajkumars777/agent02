$sourceDir = "c:\Users\rajak\Music\Agent02"
$tempDir = "$env:TEMP\Agent02_Payload_Temp"
$payloadFile = "c:\Users\rajak\Music\Agent02\payload.zip"

If (Test-Path $tempDir) { Remove-Item -Recurse -Force $tempDir }
If (Test-Path $payloadFile) { Remove-Item -Force $payloadFile }

New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
New-Item -ItemType Directory -Force -Path "$tempDir\backend" | Out-Null
New-Item -ItemType Directory -Force -Path "$tempDir\src" | Out-Null
New-Item -ItemType Directory -Force -Path "$tempDir\public" | Out-Null

# 1. Ensure the app is built
# (Uncomment if you want to force rebuild every time)
# & "$PSScriptRoot\build_all.ps1"

# 2. Copy compiled Electron app (win-unpacked)
$compiledAppDir = Join-Path $sourceDir "dist\win-unpacked"
if (-Not (Test-Path $compiledAppDir)) {
    Write-Error "Compiled app not found at $compiledAppDir. Please run build_all.ps1 first."
    exit 1
}

Write-Host "Copying compiled app to payload temp..."
Copy-Item "$compiledAppDir\*" $tempDir -Recurse

# 3. Add any extra root files if needed
Copy-Item "$sourceDir\.env.local" "$tempDir"

Write-Host "Zipping payload..."
Compress-Archive -Path "$tempDir\*" -DestinationPath $payloadFile -Force
Write-Host "Created payload.zip successfully."

Remove-Item -Recurse -Force $tempDir
