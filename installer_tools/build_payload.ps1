$sourceDir = "c:\Users\rajak\Music\Agent02"
$tempDir = "$env:TEMP\Agent02_Payload_Temp"
$payloadFile = "c:\Users\rajak\Music\Agent02\payload.zip"

If (Test-Path $tempDir) { Remove-Item -Recurse -Force $tempDir }
If (Test-Path $payloadFile) { Remove-Item -Force $payloadFile }

New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
New-Item -ItemType Directory -Force -Path "$tempDir\backend" | Out-Null
New-Item -ItemType Directory -Force -Path "$tempDir\src" | Out-Null
New-Item -ItemType Directory -Force -Path "$tempDir\public" | Out-Null

# Copy primary files
Copy-Item "$sourceDir\package.json" "$tempDir"
Copy-Item "$sourceDir\tailwind.config.ts" "$tempDir"
Copy-Item "$sourceDir\tsconfig.json" "$tempDir"
Copy-Item "$sourceDir\postcss.config.mjs" "$tempDir"
Copy-Item "$sourceDir\next.config.mjs" "$tempDir"
Copy-Item "$sourceDir\components.json" "$tempDir"
Copy-Item "$sourceDir\launcher.js" "$tempDir"
Copy-Item "$sourceDir\run.bat" "$tempDir"
Copy-Item "$sourceDir\.env.local" "$tempDir"

# Copy directories recursively
Copy-Item "$sourceDir\src\*" "$tempDir\src" -Recurse
Copy-Item "$sourceDir\public\*" "$tempDir\public" -Recurse

# Copy Backend avoiding venv and cache
Copy-Item "$sourceDir\backend\*" "$tempDir\backend" -Recurse -Exclude "*__pycache__*", "*venv*"
Copy-Item "$sourceDir\backend\.env" "$tempDir\backend"

Write-Host "Zipping payload..."
Compress-Archive -Path "$tempDir\*" -DestinationPath $payloadFile
Write-Host "Created payload.zip successfully."

Remove-Item -Recurse -Force $tempDir
