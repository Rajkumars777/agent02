const { app, BrowserWindow, shell, protocol, net } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');
const fs = require('fs');

let mainWindow;
let gatewayProcess;
let backendProcess;

// Register 'app' protocol to serve static files from the 'out' directory
// This fixes absolute path issues in Next.js static exports
if (app.isPackaged) {
  protocol.registerSchemesAsPrivileged([
    { scheme: 'app', privileges: { standard: true, secure: true, allowServiceWorkers: true, supportFetchAPI: true } }
  ]);
}

function getResourcePath(...segments) {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, ...segments);
  }
  return path.join(process.cwd(), ...segments);
}

function killProcess(pid) {
  if (!pid) return;
  try {
    require('child_process').execSync(`taskkill /pid ${pid} /T /F`, { stdio: 'ignore' });
  } catch (_) {}
}

function waitForBackend(url, retries = 60, interval = 1000) {
  return new Promise((resolve, reject) => {
    const attempt = (n) => {
      http.get(url, (res) => {
        if (res.statusCode < 500) resolve();
        else retry(n);
      }).on('error', () => retry(n));
    };
    const retry = (n) => {
      if (n >= retries) return reject(new Error('Backend did not start in time'));
      setTimeout(() => attempt(n + 1), interval);
    };
    attempt(0);
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    titleBarStyle: 'hidden',
    titleBarOverlay: {
      color: '#09090b',
      symbolColor: '#ffffff',
    },
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      // Need this for some cross-origin AI API calls if bypass is needed
      webSecurity: true, 
    },
    show: false,
    backgroundColor: '#09090b',
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  if (app.isPackaged) {
    // Load from our custom protocol
    mainWindow.loadURL('app://./index.html');
  } else {
    mainWindow.loadURL('http://localhost:3000');
  }

  mainWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
    console.error(`Page failed to load: ${errorCode} ${errorDescription}`);
    // If it's a black screen, showing devtools helps find the JS error
    if (app.isPackaged) mainWindow.webContents.openDevTools();
  });

  mainWindow.once('ready-to-show', () => mainWindow.show());
}

app.whenReady().then(async () => {
  // Handle 'app://' protocol calls
  if (app.isPackaged) {
    protocol.handle('app', (request) => {
      let url = request.url.substr(6); // strip 'app://'
      if (url.startsWith('./')) url = url.substr(2);
      if (url === '' || url === '/') url = 'index.html';
      
      // Sanitization to prevent directory traversal
      const filePath = path.join(__dirname, 'out', url);
      return net.fetch('file://' + filePath);
    });
  }

  // 1. Start OpenClaw Gateway
  console.log('[1/2] Starting OpenClaw Gateway...');
  gatewayProcess = spawn('cmd', ['/c', 'openclaw gateway run'], {
    detached: true,
    stdio: 'ignore',
    windowsHide: true,
  });
  gatewayProcess.unref();

  // 2. Start Python backend
  if (app.isPackaged) {
    const backendExe = getResourcePath('backend.exe');
    console.log(`[2/2] Starting backend: ${backendExe}`);
    backendProcess = spawn(backendExe, [], {
      detached: true,
      stdio: 'ignore',
      windowsHide: true,
      cwd: path.dirname(backendExe),
    });
  } else {
    console.log('[2/2] Starting backend (dev mode)...');
    backendProcess = spawn('python', ['-m', 'uvicorn', 'main:app', '--port', '8000', '--host', '127.0.0.1'], {
      cwd: path.join(process.cwd(), 'backend'),
      detached: true,
      stdio: 'ignore',
      windowsHide: true,
    });
  }
  backendProcess.unref();

  // 3. Wait for backend
  try {
    await waitForBackend('http://127.0.0.1:8000/health');
  } catch (e) {
    console.warn('Backend wait timeout:', e.message);
  }

  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  killProcess(gatewayProcess?.pid);
  killProcess(backendProcess?.pid);
});
