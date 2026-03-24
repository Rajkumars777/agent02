const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

console.log("=================================================");
console.log("       Installing Agent02 - Please Wait...       ");
console.log("=================================================");

// The destination is Local AppData
const destDir = path.join(process.env.LOCALAPPDATA, 'Agent02');

// 1. Extract Payload
console.log("[1/5] Extracting application payload into AppData...");
if (!fs.existsSync(destDir)) fs.mkdirSync(destDir, { recursive: true });

// pkg stores assets inside the snapshot at /snapshot folder
const payloadAsset = path.join(__dirname, 'payload.zip');
const payloadTemp = path.join(process.env.TEMP, 'payload_temp.zip');

try {
    fs.copyFileSync(payloadAsset, payloadTemp);
    execSync(`powershell -noprofile -command "Expand-Archive -Path '${payloadTemp}' -DestinationPath '${destDir}' -Force"`, { stdio: 'inherit' });
    fs.unlinkSync(payloadTemp);
} catch (e) {
    console.error("Failed to extract payload: ", e);
}

// 2. Check Node.js
console.log("[2/5] Checking Node.js Environment...");
try {
    execSync('node -v', { stdio: 'ignore' });
    console.log("-> Node.js installed natively.");
} catch (e) {
    console.log("-> Node.js not found. Downloading and installing Node.js silently (this may take a minute).");
    try {
        const nodeInstaller = path.join(process.env.TEMP, 'node_installer.msi');
        execSync(`powershell -command "Invoke-WebRequest -Uri 'https://nodejs.org/dist/v20.12.2/node-v20.12.2-x64.msi' -OutFile '${nodeInstaller}'"`);
        execSync(`msiexec /i "${nodeInstaller}" /qn /norestart`);
        console.log("-> Node.js installed successfully!");
    } catch (err) {
        console.error("Failed to install Node.js automatically.");
    }
}

// 3. Check Python
console.log("[3/5] Checking Python Environment...");
try {
    execSync('python --version', { stdio: 'ignore' });
    console.log("-> Python installed natively.");
} catch (e) {
    console.log("-> Python not found. Downloading and installing Python silently (this may take a minute).");
    try {
        const pythonInstaller = path.join(process.env.TEMP, 'python_installer.exe');
        execSync(`powershell -command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '${pythonInstaller}'"`);
        execSync(`"${pythonInstaller}" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0`);
        console.log("-> Python installed successfully!");
    } catch (err) {
        console.error("Failed to install Python automatically.");
    }
}

// 4. Install Dependencies
console.log("[4/5] Installing Libraries (this may take a few minutes)...");
// We run this in a new powershell process so it naturally picks up newly installed paths
try {
    const installScript = `
        cd '${destDir}'
        Write-Host 'Fetching Next.js packages...'
        cmd /c "npm install --silent"
        Write-Host 'Fetching Python Backend packages...'
        cd backend
        cmd /c "python -m pip install -r requirements.txt --quiet"
        Write-Host 'Setting up OpenClaw Gateway globally...'
        cmd /c "npm install -g openclaw-cli"
        Write-Host 'Configuring Core Gateway Intelligence...'
        cmd /c "openclaw auth set-secret openai YOUR_OPENAI_API_KEY_HERE"
        cmd /c "openclaw config set aiProvider openai"
        cmd /c "openclaw config set agents.defaults.model.primary openai/gpt-4o"
        cmd /c "openclaw config set gateway.nodes.denyCommands []"
    `;
    const psScriptPath = path.join(process.env.TEMP, 'agent02_install_deps.ps1');
    fs.writeFileSync(psScriptPath, installScript);
    execSync(`powershell -ExecutionPolicy Bypass -File "${psScriptPath}"`, { stdio: 'inherit' });
} catch (e) {
    console.log("Dependency installation encountered an issue, but we'll try to proceed anyway.");
}

// 5. Create Desktop Shortcut
console.log("[5/5] Creating Desktop Shortcut...");
try {
    const shortcutScript = `
        $WshShell = New-Object -comObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\\Agent02.lnk')
        $Shortcut.TargetPath = '${destDir}\\run.bat'
        $Shortcut.WorkingDirectory = '${destDir}'
        $Shortcut.Description = 'OpenClaw Agent Launcher'
        $Shortcut.IconLocation = "$env:SystemRoot\\System32\\imageres.dll, 2"
        $Shortcut.Save()
    `;
    const scPath = path.join(process.env.TEMP, 'make_shortcut.ps1');
    fs.writeFileSync(scPath, shortcutScript);
    execSync(`powershell -ExecutionPolicy Bypass -File "${scPath}"`, { stdio: 'ignore' });
} catch(e) {}

console.log("=================================================");
console.log("             Installation Complete!              ");
console.log("   Launch 'Agent02' from your Desktop anytime!   ");
console.log("=================================================");

// Leave cmd window open for 10 seconds so user can read message
setTimeout(() => { process.exit(0); }, 10000);
