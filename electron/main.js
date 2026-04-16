/**
 * NEXUS Desktop — Electron Main Process
 * WhatsApp-style native desktop application
 */

const { app, BrowserWindow, Tray, Menu, nativeImage, ipcMain, shell } = require('electron');
const path   = require('path');
const { spawn } = require('child_process');
const http   = require('http');
const os     = require('os');
const fs     = require('fs');

// ─── Single Instance Lock ──────────────────────────────────────────────────────
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) { app.quit(); process.exit(0); }

// ─── Constants ────────────────────────────────────────────────────────────────
const IS_DEV        = !app.isPackaged;
const BACKEND_PORT  = 8000;
const HEALTH_URL    = `http://127.0.0.1:${BACKEND_PORT}/health`;
const APP_DIR       = path.join(os.homedir(), 'AppData', 'Local', 'NEXUS');
const ICON_PATH     = path.join(__dirname, 'icon.ico');
const LOG_PATH      = path.join(APP_DIR, 'electron.log');

fs.mkdirSync(APP_DIR, { recursive: true });

function log(msg) {
  const line = `[${new Date().toISOString()}] ${msg}\n`;
  process.stdout.write(line);
  try { fs.appendFileSync(LOG_PATH, line); } catch (_) {}
}

// ─── Process Handles ──────────────────────────────────────────────────────────
let backendProc   = null;
let openclawProc  = null;
let mainWindow    = null;
let splashWindow  = null;
let tray          = null;
let isQuitting    = false;

// ─── Find Python ──────────────────────────────────────────────────────────────
function findPython() {
  const projectRoot = IS_DEV
    ? path.join(__dirname, '..')
    : path.join(process.resourcesPath);

  // Packaged: bundled backend exe
  if (app.isPackaged) {
    const bundled = path.join(process.resourcesPath, 'backend', 'nexus_backend.exe');
    if (fs.existsSync(bundled)) {
      return { cmd: bundled, args: [], cwd: path.dirname(bundled) };
    }
  }

  // Dev: venv python
  const venvPython = path.join(projectRoot, 'backend', 'venv', 'Scripts', 'python.exe');
  const mainScript = path.join(projectRoot, 'backend', 'main.py');
  if (fs.existsSync(venvPython)) {
    return { cmd: venvPython, args: [mainScript], cwd: path.join(projectRoot, 'backend') };
  }

  return { cmd: 'python', args: [mainScript], cwd: path.join(projectRoot, 'backend') };
}

// ─── Start Backend ────────────────────────────────────────────────────────────
function startBackend() {
  return new Promise((resolve, reject) => {
    const { cmd, args, cwd } = findPython();
    log(`Starting backend: ${cmd} ${args.join(' ')}`);

    backendProc = spawn(cmd, args, {
      cwd,
      windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: {
        ...process.env,
        NEXUS_CONFIG_PATH:  path.join(APP_DIR, 'config.json'),
        // Always serve the bundled out/ — never the stale AppData copy
        NEXUS_STATIC_DIR:   app.isPackaged
          ? path.join(process.resourcesPath, 'out')
          : path.join(__dirname, '..', 'out'),
        PYTHONUNBUFFERED:   '1',
      },
    });

    const logFile = fs.createWriteStream(path.join(APP_DIR, 'backend.log'), { flags: 'a' });
    backendProc.stdout.pipe(logFile);
    backendProc.stderr.pipe(logFile);

    backendProc.on('error', (err) => {
      log(`Backend spawn error: ${err.message}`);
      reject(err);
    });

    backendProc.on('exit', (code) => {
      if (!isQuitting) log(`Backend exited with code ${code}`);
    });

    // Poll health — resolve as soon as server responds
    const MAX_WAIT_MS = 20000;
    const POLL_MS     = 150;
    let elapsed = 0;

    function poll() {
      http.get(HEALTH_URL, (res) => {
        if (res.statusCode === 200) {
          log('Backend ready OK');
          resolve();
        } else {
          retry();
        }
        res.resume();
      }).on('error', () => retry());
    }

    function retry() {
      elapsed += POLL_MS;
      if (elapsed >= MAX_WAIT_MS) {
        reject(new Error('Backend did not start within 20s'));
      } else {
        setTimeout(poll, POLL_MS);
      }
    }

    // Short head-start so process has time to bind
    setTimeout(poll, 300);
  });
}

// ─── Start OpenClaw ───────────────────────────────────────────────────────────
function startOpenclaw() {
  try {
    const projectRoot = IS_DEV
      ? path.join(__dirname, '..')
      : path.join(process.resourcesPath);

    // 1. Bundled node.exe + openclaw.mjs
    const nodeExe = path.join(projectRoot, 'bin', 'node', 'node.exe');
    const clawMjs = path.join(projectRoot, 'node_modules', 'openclaw', 'openclaw.mjs');

    if (fs.existsSync(nodeExe) && fs.existsSync(clawMjs)) {
      log('Starting openclaw (bundled node)');
      openclawProc = spawn(nodeExe, [clawMjs, 'gateway', 'run'], {
        cwd: projectRoot,
        windowsHide: true,
        stdio: 'ignore',
        shell: false,
      });
    } else {
      // 2. Global openclaw — Windows .cmd needs shell:true
      log('Starting openclaw (global, shell:true)');
      openclawProc = spawn('openclaw', ['gateway', 'run'], {
        cwd: projectRoot,
        windowsHide: true,
        stdio: 'ignore',
        shell: true,   // Required for .cmd scripts on Windows
      });
    }

    openclawProc.on('error', (err) => log(`OpenClaw error: ${err.message}`));
    openclawProc.on('exit',  (code) => { if (!isQuitting) log(`OpenClaw exited: ${code}`); });
  } catch (e) {
    log(`OpenClaw start skipped: ${e.message}`);
  }
}

// ─── Create Splash Screen ─────────────────────────────────────────────────────
function createSplash() {
  splashWindow = new BrowserWindow({
    width:          480,
    height:         320,
    frame:          false,
    transparent:    true,
    resizable:      false,
    alwaysOnTop:    true,
    skipTaskbar:    true,
    webPreferences: { nodeIntegration: false },
    ...(fs.existsSync(ICON_PATH) ? { icon: ICON_PATH } : {}),
  });
  splashWindow.loadFile(path.join(__dirname, 'splash.html'));
  splashWindow.center();
}

// ─── Create Main Window ───────────────────────────────────────────────────────
function createMainWindow() {
  mainWindow = new BrowserWindow({
    width:           1280,
    height:          800,
    minWidth:        900,
    minHeight:       600,
    show:            false,
    // Native OS window frame
    frame:           true,
    autoHideMenuBar: true,
    backgroundColor: '#0a0a0f',
    webPreferences: {
      nodeIntegration:  false,
      contextIsolation: true,
      preload:          path.join(__dirname, 'preload.js'),
      webSecurity:      true,
    },
    ...(fs.existsSync(ICON_PATH) ? { icon: ICON_PATH } : {}),
  });

  mainWindow.setMenuBarVisibility(false);
  mainWindow.loadURL(`http://127.0.0.1:${BACKEND_PORT}`);

  // Notify renderer when window maximize state changes (for the title bar icon)
  mainWindow.on('maximize',   () => mainWindow.webContents.send('window-maximized'));
  mainWindow.on('unmaximize', () => mainWindow.webContents.send('window-unmaximized'));

  mainWindow.once('ready-to-show', () => {
    if (splashWindow && !splashWindow.isDestroyed()) {
      splashWindow.destroy();
      splashWindow = null;
    }
    mainWindow.show();
    mainWindow.focus();
    log('Main window shown OK');
  });

  // Close button -> minimize to tray (like WhatsApp)
  mainWindow.on('close', (e) => {
    if (!isQuitting) {
      e.preventDefault();
      mainWindow.hide();
    }
  });

  mainWindow.on('closed', () => { mainWindow = null; });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http') && !url.includes('127.0.0.1')) {
      shell.openExternal(url);
      return { action: 'deny' };
    }
    return { action: 'allow' };
  });
}

// ─── Create System Tray ───────────────────────────────────────────────────────
function createTray() {
  let trayIcon;
  if (fs.existsSync(ICON_PATH)) {
    trayIcon = nativeImage.createFromPath(ICON_PATH);
  } else {
    trayIcon = nativeImage.createEmpty();
  }

  tray = new Tray(trayIcon);
  tray.setToolTip('NEXUS Agent');

  const menu = Menu.buildFromTemplate([
    {
      label: 'Open NEXUS',
      click: () => { if (mainWindow) { mainWindow.show(); mainWindow.focus(); } },
    },
    { type: 'separator' },
    {
      label: 'Quit NEXUS',
      click: () => { isQuitting = true; app.quit(); },
    },
  ]);

  tray.setContextMenu(menu);
  tray.on('click', () => {
    if (!mainWindow) return;
    mainWindow.isVisible() ? mainWindow.hide() : (mainWindow.show(), mainWindow.focus());
  });
}

// ─── IPC Handlers ─────────────────────────────────────────────────────────────
ipcMain.on('window-minimize', () => mainWindow && mainWindow.minimize());
ipcMain.on('window-maximize', () => {
  if (!mainWindow) return;
  mainWindow.isMaximized() ? mainWindow.unmaximize() : mainWindow.maximize();
});
ipcMain.on('window-close', () => mainWindow && mainWindow.hide());
ipcMain.handle('is-maximized', () => (mainWindow ? mainWindow.isMaximized() : false));

// ─── App Lifecycle ────────────────────────────────────────────────────────────
app.on('second-instance', () => {
  if (mainWindow) { mainWindow.show(); mainWindow.focus(); }
});

app.whenReady().then(async () => {
  log('=== NEXUS Desktop starting ===');

  createSplash();
  createTray();

  // Start both services in parallel
  startOpenclaw();

  try {
    await startBackend();
  } catch (err) {
    log(`Backend start failed: ${err.message} — continuing anyway`);
  }

  createMainWindow();
});

app.on('activate', () => {
  if (mainWindow) { mainWindow.show(); mainWindow.focus(); }
});

app.on('before-quit', () => { isQuitting = true; });

app.on('will-quit', () => {
  log('=== NEXUS shutting down ===');
  try { if (backendProc)  backendProc.kill('SIGTERM');  } catch (_) {}
  try { if (openclawProc) openclawProc.kill('SIGTERM'); } catch (_) {}
});
