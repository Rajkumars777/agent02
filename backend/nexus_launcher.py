"""
nexus_launcher.py — NEXUS Desktop Application Launcher
=======================================================
PyInstaller entry point. This is what gets compiled into NEXUS.exe.

On first run:
  1. Extracts app data to %LOCALAPPDATA%\\NEXUS
  2. Configures OpenClaw with the user's API key (via a GUI prompt)
  3. Starts OpenClaw gateway (using bundled portable Node.js)
  4. Starts FastAPI backend (serving both API + Next.js static files)
  5. Opens the browser to http://localhost:8000
  6. Shows a system tray icon for control

On subsequent runs:
  1-2 skipped (config already exists)
  3-6 same as above
"""

import sys
import os
import subprocess
import threading
import time
import json
import webbrowser
import secrets
import shutil
import zipfile
import urllib.request
import platform
import signal
import atexit

# ─── Paths ───────────────────────────────────────────────────────────────────

APP_DIR = os.path.join(os.path.expanduser("~"), "AppData", "Local", "NEXUS")
NODE_DIR = os.path.join(APP_DIR, "node")
OPENCLAW_BIN = os.path.join(NODE_DIR, "openclaw", "bin", "openclaw.js")
NODE_EXE = os.path.join(NODE_DIR, "node.exe")
NPM_CMD = os.path.join(NODE_DIR, "npm.cmd")
OPENCLAW_CONFIG = os.path.join(os.path.expanduser("~"), ".openclaw", "openclaw.json")
CONFIG_FILE = os.path.join(APP_DIR, "config.json")
LOG_FILE = os.path.join(APP_DIR, "nexus.log")

# Source dir (inside PyInstaller bundle or dev folder)
if getattr(sys, "frozen", False):
    SRC_DIR = sys._MEIPASS
else:
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))

STATIC_DIR = os.path.join(APP_DIR, "out")  # Next.js static build

# Portable Node.js download (Windows x64, LTS)
NODE_VERSION = "v22.13.1"
NODE_ZIP_URL = f"https://nodejs.org/dist/{NODE_VERSION}/node-{NODE_VERSION}-win-x64.zip"
NODE_ZIP_NAME = f"node-{NODE_VERSION}-win-x64"

# Tracked subprocesses for cleanup
_procs = []


# ─── Logging ─────────────────────────────────────────────────────────────────

def log(msg):
    ts = time.strftime("[%H:%M:%S]")
    line = f"{ts} {msg}"
    print(line, flush=True)
    try:
        os.makedirs(APP_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ─── GUI helpers (tkinter) ───────────────────────────────────────────────────

def ask_api_key():
    """Show a simple GUI dialog to collect the user's API key and provider."""
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox

        result = {"key": "", "provider": "openai", "model": "gpt-4o-mini", "ok": False}

        root = tk.Tk()
        root.title("NEXUS — First Time Setup")
        root.geometry("480x340")
        root.resizable(False, False)
        root.configure(bg="#0f0f0f")

        # Try dark window chrome on Windows
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(1)), 4)
        except Exception:
            pass

        root.eval("tk::PlaceWindow . center")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TLabel", background="#0f0f0f", foreground="#e5e5e5", font=("Segoe UI", 10))
        style.configure("TEntry", fieldbackground="#1a1a1a", foreground="#e5e5e5", bordercolor="#333")
        style.configure("TCombobox", fieldbackground="#1a1a1a", foreground="#e5e5e5", background="#1a1a1a")
        style.configure("TButton", background="#6366f1", foreground="white", font=("Segoe UI", 10, "bold"))
        style.map("TButton", background=[("active", "#4f46e5")])

        pad = dict(padx=20, pady=6)

        ttk.Label(root, text="NEXUS  ·  First Time Setup", font=("Segoe UI", 14, "bold"),
                  foreground="#6366f1", background="#0f0f0f").pack(pady=(20, 4))
        ttk.Label(root, text="Enter your AI API key to get started",
                  foreground="#888", background="#0f0f0f").pack(pady=(0, 16))

        # Provider
        ttk.Label(root, text="AI Provider").pack(anchor="w", **pad)
        provider_var = tk.StringVar(value="openai")
        model_var = tk.StringVar(value="gpt-4o-mini")

        def on_provider_change(*_):
            p = provider_var.get()
            if p == "openai":
                model_var.set("gpt-4o-mini")
                key_hint.config(text="Paste your sk-... key from platform.openai.com")
            elif p == "google":
                model_var.set("gemini-2.0-flash")
                key_hint.config(text="Paste your AIza... key from aistudio.google.com")
            else:
                model_var.set("google/gemini-2.0-flash-exp:free")
                key_hint.config(text="Paste your sk-or-... key from openrouter.ai")

        combo = ttk.Combobox(root, textvariable=provider_var,
                             values=["openai", "google", "openrouter"], state="readonly", width=40)
        combo.pack(**pad)
        combo.bind("<<ComboboxSelected>>", on_provider_change)

        # API Key
        ttk.Label(root, text="API Key").pack(anchor="w", **pad)
        key_entry = ttk.Entry(root, show="•", width=42)
        key_entry.pack(**pad)
        key_hint = ttk.Label(root, text="Paste your sk-... key from platform.openai.com",
                             foreground="#555", background="#0f0f0f", font=("Segoe UI", 8))
        key_hint.pack()

        def on_submit():
            key = key_entry.get().strip()
            if not key or len(key) < 8:
                messagebox.showerror("Invalid Key", "Please enter a valid API key.", parent=root)
                return
            result["key"] = key
            result["provider"] = provider_var.get()
            result["model"] = model_var.get()
            result["ok"] = True
            root.destroy()

        def on_skip():
            log("User skipped API key setup — app will open without AI configured.")
            result["ok"] = False
            root.destroy()

        btn_frame = tk.Frame(root, bg="#0f0f0f")
        btn_frame.pack(pady=16)
        ttk.Button(btn_frame, text="Skip for now", command=on_skip).pack(side="left", padx=8)
        ttk.Button(btn_frame, text="  Connect  ", command=on_submit).pack(side="left", padx=8)

        key_entry.focus_set()
        root.bind("<Return>", lambda _: on_submit())
        root.mainloop()
        return result

    except Exception as e:
        log(f"GUI dialog failed: {e}")
        return {"ok": False}


def show_splash(message: str):
    """Simple non-blocking splash text window."""
    try:
        import tkinter as tk
        splash = tk.Tk()
        splash.overrideredirect(True)
        splash.geometry("400x100")
        splash.configure(bg="#0f0f0f")
        splash.eval("tk::PlaceWindow . center")
        lbl = tk.Label(splash, text=message, bg="#0f0f0f", fg="#6366f1",
                       font=("Segoe UI", 11, "bold"), wraplength=380)
        lbl.pack(expand=True)
        splash.update()
        return splash
    except Exception:
        return None


def close_splash(splash):
    try:
        if splash:
            splash.destroy()
    except Exception:
        pass


# ─── Dependency Setup ────────────────────────────────────────────────────────

def ensure_app_dir():
    """Extract bundled files from PyInstaller bundle to APP_DIR on first run."""
    os.makedirs(APP_DIR, exist_ok=True)

    # Copy Next.js static build
    bundled_out = os.path.join(SRC_DIR, "out")
    if os.path.isdir(bundled_out) and not os.path.isdir(STATIC_DIR):
        log("Extracting frontend files...")
        shutil.copytree(bundled_out, STATIC_DIR)
        log(f"Frontend extracted to {STATIC_DIR}")


def ensure_node():
    """Download portable Node.js if not already present or outdated."""
    needs_download = not os.path.exists(NODE_EXE)
    
    if not needs_download:
        # Check version
        try:
            res = subprocess.run([NODE_EXE, "--version"], capture_output=True, text=True, check=True)
            current_v = res.stdout.strip()
            log(f"Current Node.js version: {current_v}")
            # If current version is < 22, force update
            if int(current_v.split('.')[0].replace('v', '')) < 22:
                log(f"Node.js version {current_v} is too old (v22.12+ required). Forcing update to {NODE_VERSION}...")
                shutil.rmtree(NODE_DIR, ignore_errors=True)
                needs_download = True
        except Exception as e:
            log(f"Failed to check Node.js version: {e}. Forcing re-download.")
            shutil.rmtree(NODE_DIR, ignore_errors=True)
            needs_download = True

    if not needs_download:
        log(f"Node.js already present at {NODE_DIR}")
        return

    log(f"Downloading portable Node.js {NODE_VERSION}...")
    zip_path = os.path.join(APP_DIR, "node.zip")

    splash = show_splash(f"Downloading Node.js {NODE_VERSION} (first time setup)...")

    try:
        def reporthook(count, block_size, total_size):
            if total_size > 0 and count % 100 == 0:
                mb = count * block_size / (1024 * 1024)
                log(f"  Download progress: {mb:.1f} MB")

        urllib.request.urlretrieve(NODE_ZIP_URL, zip_path, reporthook)
        log("Node.js downloaded. Extracting...")

        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(APP_DIR)

        # Rename extracted folder to "node"
        extracted = os.path.join(APP_DIR, NODE_ZIP_NAME)
        if os.path.exists(extracted):
            os.rename(extracted, NODE_DIR)

        os.remove(zip_path)
        log(f"Node.js ready at {NODE_DIR}")
    finally:
        close_splash(splash)


def ensure_openclaw():
    """Install openclaw globally into APP_DIR/node/node_modules using bundled npm."""
    openclaw_dir = os.path.join(NODE_DIR, "node_modules", "openclaw")
    if os.path.exists(openclaw_dir):
        log("OpenClaw already installed.")
        return

    log("Installing OpenClaw via bundled npm...")
    splash = show_splash("Installing OpenClaw (first time setup — ~30 seconds)...")

    try:
        npm = os.path.join(NODE_DIR, "npm.cmd")
        env = os.environ.copy()
        env["PATH"] = NODE_DIR + os.pathsep + env.get("PATH", "")

        result = subprocess.run(
            [npm, "install", "-g", "openclaw", "--prefix", NODE_DIR],
            capture_output=True, text=True, env=env, shell=True
        )
        if result.returncode != 0:
            log(f"npm install failed: {result.stderr}")
            raise RuntimeError("OpenClaw installation failed")

        log("OpenClaw installed successfully.")
    finally:
        close_splash(splash)


def configure_openclaw(api_key: str, provider: str, model: str):
    """Write ~/.openclaw/openclaw.json with the user's API key."""
    openclaw_dir = os.path.join(os.path.expanduser("~"), ".openclaw")
    os.makedirs(openclaw_dir, exist_ok=True)

    workspace = os.path.join(openclaw_dir, "workspace")
    os.makedirs(workspace, exist_ok=True)

    token = secrets.token_urlsafe(32)
    if provider == "openai":
        primary_model = f"openai/{model}"
        auth_profiles = {
            "openai:default": {"provider": "openai", "mode": "api_key", "apiKey": api_key}
        }
    elif provider == "google":
        primary_model = f"google/{model}"
        auth_profiles = {
            "google:default": {"provider": "google", "mode": "api_key", "apiKey": api_key}
        }
    else:
        primary_model = f"openrouter/{model}"
        auth_profiles = {
            "openrouter:default": {"provider": "openrouter", "mode": "api_key", "apiKey": api_key}
        }

    # If config exists, update it; otherwise create fresh
    existing = {}
    if os.path.exists(OPENCLAW_CONFIG):
        try:
            with open(OPENCLAW_CONFIG, "r") as f:
                existing = json.load(f)
            # Reuse existing token if present
            token = existing.get("gateway", {}).get("auth", {}).get("token", token)
        except Exception:
            pass

    cfg = existing
    cfg["auth"] = {"profiles": auth_profiles}
    cfg["agents"] = {
        "defaults": {
            "model": {"primary": primary_model},
            "workspace": workspace,
        }
    }
    # Surgically update only the critical gateway fields so we
    # preserve any other sub-keys OpenClaw has added (tailscale, etc.)
    gw = cfg.setdefault("gateway", {})
    gw["port"] = 18789
    gw["mode"] = "local"
    gw["bind"] = "loopback"
    gw.setdefault("auth", {})["mode"] = "token"
    gw["auth"]["token"] = token          # auth.token
    gw.setdefault("remote", {})["token"] = token  # remote.token — must match
    gw.setdefault("http", {}).setdefault("endpoints", {}).setdefault(
        "chatCompletions", {})["enabled"] = True
    gw.setdefault("nodes", {})["denyCommands"] = []

    with open(OPENCLAW_CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

    log(f"OpenClaw configured at {OPENCLAW_CONFIG}")

    # Write backend config.json
    backend_config = {
        "ai_provider": "openclaw",
        "api_key": api_key,
        "ai_model": model,
        "openclaw_gateway_url": "http://localhost:18789/api/v1/message",
        "openclaw_channel": "",
        "openclaw_token": token,
        "openai_api_key": api_key if provider == "openai" else "",
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(backend_config, f, indent=2)

    # Write .env for backend
    env_path = os.path.join(APP_DIR, "backend.env")
    with open(env_path, "w") as f:
        f.write(f"OPENAI_API_KEY={api_key if provider == 'openai' else ''}\n")

    log(f"Backend config written to {CONFIG_FILE}")
    return token


def sync_tokens():
    """
    Ensure gateway.auth.token == gateway.remote.token in openclaw.json,
    and that config.json has the same token.
    If no token exists anywhere, generate a fresh one.
    """
    try:
        oc_cfg = {}
        if os.path.exists(OPENCLAW_CONFIG):
            try:
                with open(OPENCLAW_CONFIG, "r", encoding="utf-8") as f:
                    oc_cfg = json.load(f)
            except Exception:
                oc_cfg = {}

        # Find whichever token is available
        token = (
            oc_cfg.get("gateway", {}).get("auth", {}).get("token") or
            oc_cfg.get("gateway", {}).get("remote", {}).get("token")
        )

        # Also check our own config.json as a source of truth
        if not token and os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    nexus_cfg = json.load(f)
                token = nexus_cfg.get("openclaw_token", "")
            except Exception:
                pass

        # Generate a fresh token if nothing exists
        if not token:
            token = secrets.token_urlsafe(32)
            log(f"Generated new gateway token: {token[:8]}...")

        # Write matching tokens to openclaw.json
        os.makedirs(os.path.dirname(OPENCLAW_CONFIG), exist_ok=True)
        changed_oc = False
        if oc_cfg.get("gateway", {}).get("auth", {}).get("token") != token:
            oc_cfg.setdefault("gateway", {}).setdefault("auth", {})["mode"] = "token"
            oc_cfg["gateway"]["auth"]["token"] = token
            changed_oc = True
        if oc_cfg.get("gateway", {}).get("remote", {}).get("token") != token:
            oc_cfg.setdefault("gateway", {}).setdefault("remote", {})["token"] = token
            changed_oc = True
        # Ensure gateway is in local mode
        if oc_cfg.get("gateway", {}).get("port") != 18789:
            oc_cfg.setdefault("gateway", {})["port"] = 18789
            changed_oc = True
        if oc_cfg.get("gateway", {}).get("mode") != "local":
            oc_cfg.setdefault("gateway", {})["mode"] = "local"
            changed_oc = True
        if oc_cfg.get("gateway", {}).get("bind") != "loopback":
            oc_cfg.setdefault("gateway", {})["bind"] = "loopback"
            changed_oc = True

        if changed_oc:
            log("Updating openclaw.json to ensure token consistency...")
            with open(OPENCLAW_CONFIG, "w", encoding="utf-8") as f:
                json.dump(oc_cfg, f, indent=2, ensure_ascii=False)

        # Sync same token to config.json
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    nexus_cfg = json.load(f)
            except Exception:
                nexus_cfg = {}

            if nexus_cfg.get("openclaw_token") != token:
                log(f"Syncing OpenClaw token to config.json...")
                nexus_cfg["openclaw_token"] = token
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(nexus_cfg, f, indent=2)
                log("Token synced successfully.")

    except Exception as e:
        log(f"Failed to sync tokens: {e}")


# ─── Process Management ───────────────────────────────────────────────────────

def cleanup():
    log("Shutting down NEXUS services...")
    try:
        from core.openclaw_process import stop_gateway
        stop_gateway()
    except Exception:
        pass
    for p in _procs:
        try:
            if p.poll() is None:
                p.terminate()
        except Exception:
            pass
    time.sleep(1)
    for p in _procs:
        try:
            if p.poll() is None:
                p.kill()
        except Exception:
            pass


def start_openclaw_gateway():
    """Start the OpenClaw gateway using the core process manager."""
    try:
        # Add SRC_DIR and backend to sys.path so imports work
        for d in [SRC_DIR, APP_DIR, os.path.join(SRC_DIR, "backend")]:
            if d not in sys.path:
                sys.path.insert(0, d)
                
        from core.openclaw_process import start_gateway
        log("Starting OpenClaw via core manager...")
        start_gateway()
    except Exception as e:
        log(f"Failed to start OpenClaw Gateway via core: {e}")


def start_backend():
    """Start the FastAPI backend as a background thread (in-process)."""
    # Add SRC_DIR and APP_DIR to sys.path so imports work
    for d in [SRC_DIR, APP_DIR, os.path.join(SRC_DIR, "backend")]:
        if d not in sys.path:
            sys.path.insert(0, d)

    # Set config path env variable for the backend to pick up
    os.environ["NEXUS_CONFIG_PATH"] = CONFIG_FILE
    os.environ["NEXUS_STATIC_DIR"] = STATIC_DIR

    import uvicorn

    def _run():
        try:
            # Import the app — it will read NEXUS_STATIC_DIR
            from main import app
            uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning", use_colors=False)
        except Exception as e:
            log(f"Backend error: {e}")

    t = threading.Thread(target=_run, daemon=True, name="backend")
    t.start()
    log("FastAPI backend thread started")
    return t


def wait_for_gateway(timeout=30):
    import urllib.request as ur
    log("Waiting for OpenClaw Gateway (port 18789) to be ready...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            # Check if gateway is responding to basic API request
            ur.urlopen("http://127.0.0.1:18789/api/v1/health", timeout=2)
            log("OpenClaw Gateway is ready.")
            return True
        except Exception:
            time.sleep(1)
    log("OpenClaw Gateway did not start in time.")
    return False


def wait_for_backend(timeout=30):
    import urllib.request as ur
    log("Waiting for FastAPI backend (port 8000) to be ready...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            ur.urlopen("http://127.0.0.1:8000/health", timeout=2)
            log("FastAPI backend is ready.")
            return True
        except Exception:
            time.sleep(0.5)
    log("FastAPI backend did not start in time.")
    return False


# ─── Main ────────────────────────────────────────────────────────────────────

def first_run_check():
    return not os.path.exists(CONFIG_FILE)


def main():
    atexit.register(cleanup)
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    os.makedirs(APP_DIR, exist_ok=True)
    
    # Force-kill any existing gateway process on port 18789 to avoid "port in use" or "token mismatch" from old processes
    if os.name == 'nt':
        log("Ensuring port 18789 is free...")
        subprocess.run(
            'for /f "tokens=5" %a in (\'netstat -aon ^| findstr :18789 ^| findstr LISTENING\') do taskkill /F /PID %a',
            shell=True, capture_output=True
        )
    
    # Do NOT set OPENCLAW_HOME in the Python process env.
    # The Python helpers (_get_openclaw_home) resolve ~/.openclaw directly.
    # The Node.js subprocess gets its own OPENCLAW_HOME set in start_openclaw_gateway().
    
    log("=" * 50)
    log("NEXUS Desktop Application Starting...")
    log(f"APP_DIR: {APP_DIR}")
    log(f"SRC_DIR: {SRC_DIR}")

    # ── First-run setup ───────────────────────────────────────────────────────
    if first_run_check():
        log("First run detected — starting setup wizard.")

        # Ask user for API key
        result = ask_api_key()
        if result.get("ok"):
            token = configure_openclaw(result["key"], result["provider"], result["model"])
            log(f"Setup complete. Token: {token[:8]}...")
        else:
            log("Skipped API key — user can configure later in Settings.")
            # Write empty config so we don't ask again
            with open(CONFIG_FILE, "w") as f:
                json.dump({
                    "ai_provider": "openclaw",
                    "api_key": "",
                    "ai_model": "gpt-4o-mini",
                    "openclaw_gateway_url": "http://localhost:18789/api/v1/message",
                    "openclaw_channel": "",
                    "openclaw_token": "",
                    "openai_api_key": "",
                }, f, indent=2)
    else:
        log("Config found — skipping first-run setup.")
        sync_tokens()

    # ── Always ensure Node.js + OpenClaw are up to date ──────────────────────
    # (runs every launch so Node.js version upgrades are auto-applied)
    splash = show_splash("NEXUS — Checking dependencies...")
    ensure_app_dir()
    ensure_node()
    ensure_openclaw()
    close_splash(splash)

    # ── Start services ───────────────────────────────────────────────────────
    splash = show_splash("NEXUS — Starting services...")

    # Sync tokens one final time right before gateway starts
    sync_tokens()

    start_openclaw_gateway()
    wait_for_gateway(timeout=180)

    # Re-sync after gateway has started (OpenClaw may update openclaw.json on first run)
    sync_tokens()

    start_backend()
    wait_for_backend(timeout=30)

    close_splash(splash)

    # ── Open Native App Window ───────────────────────────────────────────────
    url = "http://localhost:8000"
    log(f"Opening native app window at {url}")
    
    # Try Edge (built into Windows 10/11)
    edge_cases = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    ]
    
    # Try Chrome
    chrome_cases = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    ]
    
    launched = False
    for path in edge_cases + chrome_cases:
        if os.path.exists(path):
            try:
                # --app creates a window without address bar/tabs (like WhatsApp)
                subprocess.Popen([path, f"--app={url}"])
                launched = True
                log(f"Launched using {path}")
                break
            except Exception as e:
                log(f"Failed to launch {path}: {e}")
                
    if not launched:
        log("Falling back to default browser.")
        webbrowser.open(url)

    # ── Keep alive ───────────────────────────────────────────────────────────
    log("NEXUS is running. Press Ctrl+C or close this window to stop.")
    try:
        _run_tray()
    except Exception:
        while True:
            time.sleep(5)


def _run_tray():
    """Show a system tray icon (requires pystray + Pillow)."""
    try:
        import pystray
        from PIL import Image, ImageDraw

        # Create a small icon
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse([4, 4, 60, 60], fill=(99, 102, 241, 255))
        d.text((20, 20), "N", fill="white")

        def on_open(_):
            webbrowser.open("http://localhost:8000")

        def on_quit(icon, _):
            icon.stop()
            cleanup()
            sys.exit(0)

        menu = pystray.Menu(
            pystray.MenuItem("Open NEXUS", on_open, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", on_quit),
        )
        icon = pystray.Icon("NEXUS", img, "NEXUS Agent", menu)
        icon.run()
    except ImportError:
        # pystray not available — just block
        while True:
            time.sleep(5)


if __name__ == "__main__":
    main()
