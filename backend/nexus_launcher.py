"""
nexus_launcher.py — NEXUS Desktop Application Launcher
=======================================================
PyInstaller entry point. This is what gets compiled into NEXUS.exe.

On first run:
  1. Silently auto-configures with default API key (no dialog)
  2. Extracts app data to %LOCALAPPDATA%\\NEXUS
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

# Stamp file — tracks installed Node version to skip re-download on every launch
NODE_STAMP = os.path.join(NODE_DIR, ".installed_version")

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

# ─── Default Configuration (pre-loaded API key) ───────────────────────────────

DEFAULT_API_KEY      = ""
DEFAULT_PROVIDER     = "openai"
DEFAULT_MODEL        = "gpt-5.1-codex-mini"

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


# ─── GUI helpers (tkinter) — used only for Settings, not first-run ───────────

def ask_api_key_for_settings():
    """Show a GUI dialog to let the user update API key / provider / model."""
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox

        result = {"key": DEFAULT_API_KEY, "provider": DEFAULT_PROVIDER, "model": DEFAULT_MODEL, "ok": False}

        root = tk.Tk()
        root.title("NEXUS — AI Settings")
        root.geometry("520x420")
        root.resizable(False, False)
        root.configure(bg="#0f0f0f")

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

        pad = dict(padx=20, pady=5)

        ttk.Label(root, text="NEXUS  ·  AI Model Settings", font=("Segoe UI", 14, "bold"),
                  foreground="#6366f1", background="#0f0f0f").pack(pady=(20, 4))
        ttk.Label(root, text="Update your AI provider, model, and API key",
                  foreground="#888", background="#0f0f0f").pack(pady=(0, 14))

        # Provider
        ttk.Label(root, text="AI Provider").pack(anchor="w", **pad)
        provider_var = tk.StringVar(value=DEFAULT_PROVIDER)

        # Model maps per provider
        MODEL_OPTIONS = {
            "google":      ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash",
                             "gemini-2.0-flash-lite", "gemini-1.5-pro", "gemini-1.5-flash"],
            "openai":      ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "o1", "o1-mini",
                             "o3-mini", "o4-mini"],
            "anthropic":   ["claude-opus-4-5", "claude-sonnet-4-5", "claude-haiku-3-5",
                             "claude-3-5-sonnet-20241022", "claude-3-opus-20240229"],
            "openrouter":  ["google/gemini-2.5-flash", "google/gemini-2.0-flash-exp:free",
                             "anthropic/claude-3.5-sonnet", "openai/gpt-4o",
                             "meta-llama/llama-3.3-70b-instruct:free",
                             "deepseek/deepseek-r1:free"],
            "groq":        ["llama-3.3-70b-versatile", "mixtral-8x7b-32768",
                             "gemma2-9b-it", "llama-3.1-8b-instant"],
        }

        model_var = tk.StringVar(value=DEFAULT_MODEL)
        model_combo = None

        def on_provider_change(*_):
            p = provider_var.get()
            opts = MODEL_OPTIONS.get(p, [])
            if model_combo:
                model_combo["values"] = opts
            if opts:
                model_var.set(opts[0])
            hints = {
                "google":     "Paste your AIza... key from aistudio.google.com",
                "openai":     "Paste your sk-... key from platform.openai.com",
                "anthropic":  "Paste your sk-ant-... key from console.anthropic.com",
                "openrouter": "Paste your sk-or-... key from openrouter.ai",
                "groq":       "Paste your gsk_... key from console.groq.com",
            }
            key_hint.config(text=hints.get(p, "Paste your API key"))

        providers = list(MODEL_OPTIONS.keys())
        combo = ttk.Combobox(root, textvariable=provider_var,
                             values=providers, state="readonly", width=44)
        combo.pack(**pad)
        combo.bind("<<ComboboxSelected>>", on_provider_change)

        # Model
        ttk.Label(root, text="Model").pack(anchor="w", **pad)
        model_combo = ttk.Combobox(root, textvariable=model_var,
                                   values=MODEL_OPTIONS[DEFAULT_PROVIDER], state="normal", width=44)
        model_combo.pack(**pad)

        # API Key
        ttk.Label(root, text="API Key").pack(anchor="w", **pad)
        key_entry = ttk.Entry(root, show="•", width=46)
        key_entry.pack(**pad)
        key_hint = ttk.Label(root, text="Paste your AIza... key from aistudio.google.com",
                             foreground="#555", background="#0f0f0f", font=("Segoe UI", 8))
        key_hint.pack()

        def on_save():
            key = key_entry.get().strip()
            if not key or len(key) < 8:
                messagebox.showerror("Invalid Key", "Please enter a valid API key.", parent=root)
                return
            result["key"] = key
            result["provider"] = provider_var.get()
            result["model"] = model_var.get()
            result["ok"] = True
            root.destroy()

        btn_frame = tk.Frame(root, bg="#0f0f0f")
        btn_frame.pack(pady=18)
        ttk.Button(btn_frame, text="Cancel", command=root.destroy).pack(side="left", padx=8)
        ttk.Button(btn_frame, text="  Save & Restart  ", command=on_save).pack(side="left", padx=8)

        key_entry.focus_set()
        root.bind("<Return>", lambda _: on_save())
        root.mainloop()
        return result

    except Exception as e:
        log(f"Settings dialog failed: {e}")
        return {"ok": False}


def show_splash(message: str):
    """Simple non-blocking splash text window."""
    try:
        import tkinter as tk
        splash = tk.Tk()
        splash.overrideredirect(True)
        splash.geometry("400x80")
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


def _read_stamp() -> str:
    """Read the version stamp from the installed node folder."""
    try:
        with open(NODE_STAMP, "r") as f:
            return f.read().strip()
    except Exception:
        return ""


def _write_stamp(version: str):
    """Write the version stamp so next launch can skip download."""
    try:
        with open(NODE_STAMP, "w") as f:
            f.write(version)
    except Exception:
        pass


def ensure_node():
    """Download portable Node.js only if missing or version stamp mismatches."""
    # Fast path: stamp matches → nothing to do
    if os.path.exists(NODE_EXE) and _read_stamp() == NODE_VERSION:
        log(f"Node.js {NODE_VERSION} already installed — skipping download.")
        return

    # Stamp mismatch or node.exe missing
    if os.path.exists(NODE_EXE):
        log(f"Node.js version mismatch (need {NODE_VERSION}) — updating...")
        shutil.rmtree(NODE_DIR, ignore_errors=True)
    else:
        log(f"Node.js not found — downloading {NODE_VERSION}...")

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

        extracted = os.path.join(APP_DIR, NODE_ZIP_NAME)
        if os.path.exists(extracted):
            os.rename(extracted, NODE_DIR)

        os.remove(zip_path)
        _write_stamp(NODE_VERSION)
        log(f"Node.js {NODE_VERSION} ready at {NODE_DIR}")
    finally:
        close_splash(splash)


def ensure_openclaw():
    """Install openclaw globally into APP_DIR/node/node_modules (only once)."""
    openclaw_dir = os.path.join(NODE_DIR, "node_modules", "openclaw")
    if os.path.exists(openclaw_dir):
        log("OpenClaw already installed — skipping.")
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


def ensure_kapture_mcp():
    """Install kapture-mcp (only once)."""
    kapture_dir = os.path.join(NODE_DIR, "node_modules", "kapture-mcp")
    if os.path.exists(kapture_dir):
        log("Kapture MCP already installed — skipping.")
        return

    log("Installing Kapture MCP server (browser automation)...")
    splash = show_splash("Installing Kapture MCP (first time setup — ~15 seconds)...")

    try:
        npm = os.path.join(NODE_DIR, "npm.cmd")
        if not os.path.exists(npm):
            npm = "npm"
        env = os.environ.copy()
        env["PATH"] = NODE_DIR + os.pathsep + env.get("PATH", "")

        result = subprocess.run(
            [npm, "install", "-g", "kapture-mcp", "--prefix", NODE_DIR],
            capture_output=True, text=True, env=env, shell=True
        )
        if result.returncode != 0:
            log(f"kapture-mcp install warning (non-fatal): {result.stderr[:200]}")
        else:
            log("Kapture MCP installed successfully.")
    except Exception as e:
        log(f"Kapture MCP install failed (non-fatal): {e}")
    finally:
        close_splash(splash)


# ─── Kapture MCP process ──────────────────────────────────────────────────────

_kapture_proc = None
KAPTURE_WS_PORT = 61822


def start_kapture_mcp():
    global _kapture_proc

    try:
        import urllib.request as ur
        ur.urlopen(f"http://localhost:{KAPTURE_WS_PORT}", timeout=2)
        log("Kapture MCP server already running on port 61822.")
        return
    except Exception:
        pass

    kapture_candidates = [
        os.path.join(NODE_DIR, "node_modules", ".bin", "kapture-mcp.cmd"),
        os.path.join(NODE_DIR, "node_modules", ".bin", "kapture-mcp"),
        shutil.which("kapture-mcp") or "",
    ]
    kapture_bin = next((p for p in kapture_candidates if p and os.path.exists(p)), None)

    env = os.environ.copy()
    env["PATH"] = NODE_DIR + os.pathsep + env.get("PATH", "")

    if kapture_bin:
        cmd = [kapture_bin, "server"]
    else:
        npx_cmd = os.path.join(NODE_DIR, "npx.cmd")
        if os.path.exists(npx_cmd):
            cmd = [npx_cmd, "--yes", "kapture-mcp", "server"]
        elif shutil.which("npx"):
            cmd = ["npx", "--yes", "kapture-mcp", "server"]
        else:
            log("Kapture MCP: npx not found — browser automation requires manual setup")
            return

    try:
        log(f"Starting Kapture MCP server: {' '.join(cmd)}")
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        _kapture_proc = subprocess.Popen(
            cmd,
            shell=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
            env=env,
        )
        _procs.append(_kapture_proc)
        time.sleep(3)
        log(f"Kapture MCP running (PID {_kapture_proc.pid}) at ws://localhost:61822/mcp")
        log("Open Chrome with the Kapture extension to enable browser automation.")
    except Exception as e:
        log(f"Kapture MCP start failed (non-fatal): {e}")


# ─── OpenClaw Configuration ──────────────────────────────────────────────────

def configure_openclaw(api_key: str, provider: str, model: str):
    """Write ~/.openclaw/openclaw.json with the given API key / model."""
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
    elif provider in ("google", "gemini"):
        primary_model = f"google/{model}"
        auth_profiles = {
            "google:default": {"provider": "google", "mode": "api_key", "apiKey": api_key}
        }
    elif provider == "anthropic":
        primary_model = f"anthropic/{model}"
        auth_profiles = {
            "anthropic:default": {"provider": "anthropic", "mode": "api_key", "apiKey": api_key}
        }
    elif provider == "groq":
        primary_model = f"groq/{model}"
        auth_profiles = {
            "groq:default": {"provider": "groq", "mode": "api_key", "apiKey": api_key}
        }
    else:
        # openrouter or any other
        primary_model = f"openrouter/{model}" if not model.startswith("openrouter/") else model
        auth_profiles = {
            "openrouter:default": {"provider": "openrouter", "mode": "api_key", "apiKey": api_key}
        }

    # Merge with existing config to preserve gateway token, device identity etc.
    existing = {}
    if os.path.exists(OPENCLAW_CONFIG):
        try:
            with open(OPENCLAW_CONFIG, "r") as f:
                existing = json.load(f)
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

    gw = cfg.setdefault("gateway", {})
    gw["port"] = 18789
    gw["mode"] = "local"
    gw["bind"] = "loopback"
    gw.setdefault("auth", {})["mode"] = "token"
    gw["auth"]["token"] = token
    gw.setdefault("remote", {})["token"] = token
    gw.setdefault("http", {}).setdefault("endpoints", {}).setdefault(
        "chatCompletions", {})["enabled"] = True
    gw.setdefault("nodes", {})["denyCommands"] = []

    with open(OPENCLAW_CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

    log(f"OpenClaw configured at {OPENCLAW_CONFIG}")

    # Write backend config.json
    backend_config = {
        "ai_provider": provider,
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
        if provider in ("google", "gemini"):
            f.write(f"GEMINI_API_KEY={api_key}\nGOOGLE_API_KEY={api_key}\n")
        elif provider == "openai":
            f.write(f"OPENAI_API_KEY={api_key}\n")
        elif provider == "anthropic":
            f.write(f"ANTHROPIC_API_KEY={api_key}\n")
        elif provider == "groq":
            f.write(f"GROQ_API_KEY={api_key}\n")
        else:
            f.write(f"OPENROUTER_API_KEY={api_key}\n")

    log(f"Backend config written to {CONFIG_FILE}")
    return token


def sync_tokens():
    """
    Ensure gateway.auth.token == gateway.remote.token in openclaw.json,
    and that config.json has the same token.
    Also ensures auth profiles exist in openclaw.json.
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

        # Find the canonical token
        token = (
            oc_cfg.get("gateway", {}).get("auth", {}).get("token") or
            oc_cfg.get("gateway", {}).get("remote", {}).get("token")
        )
        if not token and os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    nexus_cfg = json.load(f)
                token = nexus_cfg.get("openclaw_token", "")
            except Exception:
                pass

        if not token:
            token = secrets.token_urlsafe(32)
            log(f"Generated new gateway token: {token[:8]}...")

        # Ensure auth profiles exist
        changed_oc = False
        profiles = oc_cfg.get("auth", {}).get("profiles", {})
        if not profiles and os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    nexus_cfg = json.load(f)
                api_key = nexus_cfg.get("api_key", DEFAULT_API_KEY)
                provider = nexus_cfg.get("ai_provider", DEFAULT_PROVIDER)
                model    = nexus_cfg.get("ai_model", DEFAULT_MODEL)
                log("Auth profiles missing in openclaw.json — restoring from config...")
                configure_openclaw(api_key, provider, model)
                return  # configure_openclaw handles everything
            except Exception as e:
                log(f"Could not restore auth profiles: {e}")

        os.makedirs(os.path.dirname(OPENCLAW_CONFIG), exist_ok=True)

        if oc_cfg.get("gateway", {}).get("auth", {}).get("token") != token:
            oc_cfg.setdefault("gateway", {}).setdefault("auth", {})["mode"] = "token"
            oc_cfg["gateway"]["auth"]["token"] = token
            changed_oc = True
        if oc_cfg.get("gateway", {}).get("remote", {}).get("token") != token:
            oc_cfg.setdefault("gateway", {}).setdefault("remote", {})["token"] = token
            changed_oc = True
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

        # Sync token to config.json
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    nexus_cfg = json.load(f)
            except Exception:
                nexus_cfg = {}

            if nexus_cfg.get("openclaw_token") != token:
                log("Syncing OpenClaw token to config.json...")
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
    for d in [SRC_DIR, APP_DIR, os.path.join(SRC_DIR, "backend")]:
        if d not in sys.path:
            sys.path.insert(0, d)

    os.environ["NEXUS_CONFIG_PATH"] = CONFIG_FILE
    os.environ["NEXUS_STATIC_DIR"] = STATIC_DIR

    import uvicorn

    def _run():
        try:
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

    # Force-kill any existing gateway process on port 18789
    if os.name == "nt":
        log("Ensuring port 18789 is free...")
        subprocess.run(
            'for /f "tokens=5" %a in (\'netstat -aon ^| findstr :18789 ^| findstr LISTENING\') do taskkill /F /PID %a',
            shell=True, capture_output=True
        )

    log("=" * 50)
    log("NEXUS Desktop Application Starting...")
    log(f"APP_DIR: {APP_DIR}")
    log(f"SRC_DIR: {SRC_DIR}")

    # ── First-run: silent auto-configure (no dialog) ──────────────────────────
    if first_run_check():
        log("First run detected — auto-configuring with default API key (silent).")
        token = configure_openclaw(DEFAULT_API_KEY, DEFAULT_PROVIDER, DEFAULT_MODEL)
        log(f"Auto-setup complete. Token: {token[:8]}...")
    else:
        log("Config found — skipping first-run setup.")
        sync_tokens()

    # ── Dependency setup (fast: stamps prevent re-downloads) ──────────────────
    splash = show_splash("NEXUS — Checking dependencies...")
    ensure_app_dir()
    ensure_node()
    ensure_openclaw()
    ensure_kapture_mcp()
    close_splash(splash)

    # ── Start services ────────────────────────────────────────────────────────
    splash = show_splash("NEXUS — Starting services...")

    sync_tokens()

    start_openclaw_gateway()
    wait_for_gateway(timeout=180)

    # Re-sync after gateway starts (it may rewrite openclaw.json on first run)
    sync_tokens()

    start_backend()
    wait_for_backend(timeout=30)

    start_kapture_mcp()

    close_splash(splash)

    # ── Open Native App Window ───────────────────────────────────────────────
    url = "http://localhost:8000"
    log(f"Opening native app window at {url}")

    edge_cases = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    ]
    chrome_cases = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    ]

    launched = False
    for path in edge_cases + chrome_cases:
        if os.path.exists(path):
            try:
                subprocess.Popen([path, f"--app={url}"])
                launched = True
                log(f"Launched using {path}")
                break
            except Exception as e:
                log(f"Failed to launch {path}: {e}")

    if not launched:
        log("Falling back to default browser.")
        webbrowser.open(url)

    # ── Keep alive ────────────────────────────────────────────────────────────
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
        while True:
            time.sleep(5)


if __name__ == "__main__":
    main()
