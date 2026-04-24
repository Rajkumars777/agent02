"""
nexus_launcher.py
=================
NEXUS portable launcher — compiled into NEXUS.exe by PyInstaller.

Double-click NEXUS.exe → backend + gateway start silently → browser opens.
No Python, Node.js, or manual setup required on the target machine.
"""

import sys
import os

# ── Silence stdout/stderr if None (PyInstaller --noconsole) ──────────────────
class _NullStream:
    def write(self, *a): pass
    def flush(self): pass
    def isatty(self): return False
    def __getattr__(self, _): return None

if sys.stdout is None: sys.stdout = _NullStream()
if sys.stderr is None: sys.stderr = _NullStream()

# ── Resolve base paths ────────────────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    _EXE_DIR     = os.path.dirname(os.path.abspath(sys.executable))
    _MEIPASS_DIR = sys._MEIPASS
else:
    _EXE_DIR     = os.path.dirname(os.path.abspath(__file__))
    _MEIPASS_DIR = _EXE_DIR

# ── App data dir (logs, config) ───────────────────────────────────────────────
APP_DIR = os.path.join(os.path.expanduser("~"), "AppData", "Local", "NEXUS")
os.makedirs(APP_DIR, exist_ok=True)

# ── Logging ───────────────────────────────────────────────────────────────────
import logging
_log_file = os.path.join(APP_DIR, "nexus_launcher.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(_log_file, encoding="utf-8")],
)
log = logging.getLogger("nexus_launcher")

# ── Inject backend source dir into sys.path ───────────────────────────────────
_backend_dir = os.path.join(_MEIPASS_DIR, "backend")
if os.path.isdir(_backend_dir) and _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)
if _MEIPASS_DIR not in sys.path:
    sys.path.insert(0, _MEIPASS_DIR)

if not getattr(sys, 'frozen', False):
    _dev_backend = os.path.join(_EXE_DIR, "backend")
    if _dev_backend not in sys.path:
        sys.path.insert(0, _dev_backend)
    if _EXE_DIR not in sys.path:
        sys.path.insert(0, _EXE_DIR)

# ── Config path environment variable ─────────────────────────────────────────
_release_config = os.path.join(_EXE_DIR, "config.json")
if os.path.exists(_release_config):
    os.environ.setdefault("NEXUS_CONFIG_PATH", _release_config)

# ── Static dir environment variable ───────────────────────────────────────────
_static_candidates = [
    os.path.join(_EXE_DIR,     "out"),
    os.path.join(_MEIPASS_DIR, "out"),
]
for _sc in _static_candidates:
    if os.path.isfile(os.path.join(_sc, "index.html")):
        os.environ.setdefault("NEXUS_STATIC_DIR", _sc)
        log.info(f"Static dir: {_sc}")
        break

# ── Node / PATH injection ─────────────────────────────────────────────────────
# Bundled node.exe locations (covers both old and new PyInstaller onedir layout)
_node_found = False
_node_candidates = [
    os.path.join(_MEIPASS_DIR, "bin", "node"),
    os.path.join(_EXE_DIR,     "bin", "node"),
    os.path.join(_EXE_DIR,     "_internal", "bin", "node"),
    os.path.join(_MEIPASS_DIR, "bin", "node", "node-v22.14.0-win-x64"),
    os.path.join(_EXE_DIR,     "bin", "node", "node-v22.14.0-win-x64"),
]
for _nd in _node_candidates:
    if os.path.isfile(os.path.join(_nd, "node.exe")):
        if _nd not in os.environ.get("PATH", ""):
            os.environ["PATH"] = _nd + os.pathsep + os.environ.get("PATH", "")
        log.info(f"Bundled Node.js on PATH: {_nd}")
        _node_found = True
        break

# ── If no bundled node, check system PATH ────────────────────────────────────
if not _node_found:
    import shutil as _shutil
    if _shutil.which("node"):
        _node_found = True
        log.info("Using system Node.js from PATH")
    else:
        log.error("Node.js not found — showing install prompt")
        try:
            import ctypes
            _msg = (
                "NEXUS requires Node.js v22 or newer.\n\n"
                "Node.js was not found on this computer.\n\n"
                "Please install it from:\n"
                "  https://nodejs.org\n\n"
                "After installing Node.js, launch NEXUS again."
            )
            ctypes.windll.user32.MessageBoxW(
                0, _msg, "NEXUS — Node.js Required", 0x10 | 0x40000  # MB_ICONERROR | MB_SETFOREGROUND
            )
        except Exception:
            pass
        import webbrowser as _wb
        _wb.open("https://nodejs.org/en/download")
        import os as _os
        _os._exit(1)

# ── Backend host/port ─────────────────────────────────────────────────────────
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8000
BACKEND_URL  = f"http://{BACKEND_HOST}:{BACKEND_PORT}"
READY_URL    = f"{BACKEND_URL}/nexus-ready"

# ─────────────────────────────────────────────────────────────────────────────
# Gateway pre-warm thread
# Start openclaw install / verification IMMEDIATELY so it's ready
# by the time the backend finishes its own startup.
# ─────────────────────────────────────────────────────────────────────────────

def _prewarm_gateway():
    """
    Run _ensure_openclaw() as early as possible so the npm install (if needed)
    completes before the backend's lifespan tries to start the gateway.
    This runs in parallel with backend startup.
    """
    try:
        import core.openclaw_process as _oc
        # Reset validation cache so we re-check on each app launch
        _oc._validated_script = None
        log.info("Pre-warming openclaw…")
        ok = _oc._ensure_openclaw()
        log.info(f"openclaw pre-warm: {'OK' if ok else 'failed (will retry at gateway start)'}")
    except Exception as e:
        log.warning(f"Gateway pre-warm error (non-fatal): {e}")


# ─────────────────────────────────────────────────────────────────────────────
# System Tray icon
# ─────────────────────────────────────────────────────────────────────────────

def _make_tray_image():
    try:
        from PIL import Image, ImageDraw
        img  = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([2, 2, 62, 62], fill=(88, 28, 135, 255))
        draw.line([(16, 16), (16, 48)], fill="white", width=5)
        draw.line([(16, 16), (48, 48)], fill="white", width=5)
        draw.line([(48, 16), (48, 48)], fill="white", width=5)
        return img
    except Exception:
        return None


def _run_tray(stop_event):
    try:
        import pystray
        img = _make_tray_image()
        if img is None:
            stop_event.wait()
            return

        def _open_browser(_icon, _item):
            import webbrowser
            webbrowser.open(BACKEND_URL)

        def _quit(_icon, _item):
            _icon.stop()
            stop_event.set()

        menu = pystray.Menu(
            pystray.MenuItem("Open NEXUS",  _open_browser, default=True),
            pystray.MenuItem("Quit NEXUS",  _quit),
        )
        icon = pystray.Icon("NEXUS", img, "NEXUS Agent", menu)
        log.info("System tray started")
        icon.run()
    except Exception as e:
        log.warning(f"Tray not available: {e}")
        stop_event.wait()


# ─────────────────────────────────────────────────────────────────────────────
# Backend thread
# ─────────────────────────────────────────────────────────────────────────────

def _start_backend():
    try:
        import uvicorn
        from main import app  # backend/main.py
        log.info("Starting uvicorn server…")
        uvicorn.run(
            app,
            host=BACKEND_HOST,
            port=BACKEND_PORT,
            log_level="warning",
            use_colors=False,
            access_log=False,
            loop="asyncio",
        )
    except Exception as e:
        log.error(f"Backend failed to start: {e}")
        import traceback
        log.error(traceback.format_exc())


# ─────────────────────────────────────────────────────────────────────────────
# Wait for backend ready
# ─────────────────────────────────────────────────────────────────────────────

def _wait_for_backend(timeout: int = 120) -> bool:
    """Poll /nexus-ready until the backend responds or timeout expires."""
    import time, urllib.request, urllib.error
    deadline = time.time() + timeout
    log.info(f"Waiting for backend at {READY_URL} …")
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(READY_URL, timeout=3) as resp:
                if resp.status == 200:
                    log.info("Backend is ready ✅")
                    return True
        except Exception:
            pass
        time.sleep(0.75)
    log.error("Backend did not become ready in time ❌")
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    import threading, webbrowser

    stop_event = threading.Event()

    # 1️⃣  Pre-warm: start openclaw install check immediately (parallel)
    prewarm_thread = threading.Thread(
        target=_prewarm_gateway, daemon=True, name="nexus-prewarm"
    )
    prewarm_thread.start()
    log.info("Gateway pre-warm thread started")

    # 2️⃣  Start backend
    backend_thread = threading.Thread(
        target=_start_backend, daemon=True, name="nexus-backend"
    )
    backend_thread.start()
    log.info("Backend thread started")

    # 3️⃣  Wait for backend ready, then open browser
    def _open_when_ready():
        ready = _wait_for_backend(timeout=120)
        log.info(f"Opening browser → {BACKEND_URL} (ready={ready})")
        webbrowser.open(BACKEND_URL)

    opener_thread = threading.Thread(
        target=_open_when_ready, daemon=True, name="nexus-opener"
    )
    opener_thread.start()

    # 4️⃣  System tray keeps the process alive
    _run_tray(stop_event)

    log.info("NEXUS launcher exiting")
    import os as _os
    _os._exit(0)


if __name__ == "__main__":
    main()
