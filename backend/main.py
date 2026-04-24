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

# ── Portable Lib/ path injection (thin-launcher: deps installed to ../Lib/) ───
# When running from a portable release without a venv, the launcher installs
# all packages to <release>/Lib/ and sets PYTHONPATH accordingly.
_lib_dir = os.environ.get("PYTHONPATH", "").split(os.pathsep)[0]
if _lib_dir and os.path.isdir(_lib_dir) and _lib_dir not in sys.path:
    sys.path.insert(0, _lib_dir)
# Also check sibling Lib/ relative to this file
_sibling_lib = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Lib")
if os.path.isdir(_sibling_lib) and _sibling_lib not in sys.path:
    sys.path.insert(0, os.path.abspath(_sibling_lib))

# ── Global Excepthook (catch early crashes) ──────────────────────────────────
APP_DIR = os.path.join(os.path.expanduser("~"), "AppData", "Local", "NEXUS")
os.makedirs(APP_DIR, exist_ok=True)

def _global_excepthook(exc_type, exc_value, traceback):
    import datetime
    import traceback as tb
    _fatal = os.path.join(APP_DIR, "nexus_fatal.log")
    try:
        with open(_fatal, "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.datetime.now()}] FATAL UNCAUGHT EXCEPTION:\n")
            tb.print_exception(exc_type, exc_value, traceback, file=f)
    except: pass

sys.excepthook = _global_excepthook

# ── Script and Root directory setup ───────────────────────────────────────────
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

if getattr(sys, 'frozen', False):
    _base = sys._MEIPASS
    _exe  = os.path.dirname(sys.executable)
    if _exe not in sys.path:
        sys.path.insert(0, _exe)
else:
    # In release mode, the root is parent of backend (where out/ is)
    _base = os.path.dirname(_script_dir)
    if _base not in sys.path:
        sys.path.insert(0, _base)

base_path = _base

# ── Config path (injected by nexus_launcher before uvicorn starts) ────────────
_cfg = os.environ.get("NEXUS_CONFIG_PATH", os.path.join(APP_DIR, "config.json"))
if os.path.exists(_cfg):
    os.environ.setdefault("NEXUS_CONFIG_PATH", _cfg)

# ── Minimal logging (warning only — speeds up startup) ───────────────────────
import logging
_log_file = os.path.join(APP_DIR, "nexus_backend.log")
os.makedirs(APP_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.FileHandler(_log_file, encoding='utf-8')],
)
logger = logging.getLogger(__name__)

# ── FastAPI app ───────────────────────────────────────────────────────────────
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import time

_last_heartbeat = time.time()
_heartbeat_received = False

# Import all routers at module level so FastAPI registers them correctly.
# (include_router inside lifespan is silently ignored by FastAPI's route compiler)
from api.routers import agent    as agent_router
from api.routers import events   as events_router
from api.routers import settings as settings_router
from api.routers import openclaw as openclaw_router
from api.routers import tools    as tools_router
from api.routers import system   as system_router
from api.routers import voice    as voice_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Auto-start OpenClaw gateway in background ─────────────────────────────
    import threading
    import asyncio
    
    def _auto_start_gateway():
        try:
            from core.openclaw_process import start_gateway, _is_gateway_alive
            if not _is_gateway_alive():
                logger.warning("Auto-starting OpenClaw gateway...")
                result = start_gateway()
                logger.warning(f"OpenClaw gateway auto-start: {result.get('status', 'unknown')}")
            else:
                logger.warning("OpenClaw gateway already running.")
        except Exception as e:
            logger.warning(f"Gateway auto-start error: {e}")

    threading.Thread(target=_auto_start_gateway, daemon=True).start()
    
    async def _lifespan_monitor():
        global _last_heartbeat, _heartbeat_received
        import time, os
        await asyncio.sleep(15)  # startup grace period
        while True:
            await asyncio.sleep(5)
            # If UI has loaded but no requests received for 75 seconds, auto-shutdown
            if _heartbeat_received and (time.time() - _last_heartbeat > 75):
                logger.warning("No heartbeat from UI for 75s. Shutting down automatically.")
                os._exit(0)

    monitor_task = asyncio.create_task(_lifespan_monitor())

    logger.warning("NEXUS backend ready.")
    yield
    # Gracefully close the browser-use Playwright browser (if it was used)
    # so no zombie chrome.exe processes are left after the backend exits.
    try:
        from capabilities.browser_use_client import browser_client
        await browser_client.close()
    except Exception as _e:
        logger.warning(f"[BrowserUse] Shutdown cleanup skipped: {_e}")
    logger.warning("NEXUS backend shutting down.")

app = FastAPI(lifespan=lifespan, title="NEXUS Agent Backend", docs_url=None, redoc_url=None)

# Register all routers
app.include_router(agent_router.router)
app.include_router(events_router.router)
app.include_router(settings_router.router)
app.include_router(openclaw_router.router)
app.include_router(tools_router.router)
app.include_router(system_router.router)
app.include_router(voice_router.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def heartbeat_middleware(request: Request, call_next):
    global _last_heartbeat, _heartbeat_received
    _last_heartbeat = time.time()
    _heartbeat_received = True
    return await call_next(request)

# ── /health — responds immediately ───────────────────────────────────────────
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# ── /nexus-ready — unique endpoint only the RELEASE backend has ───────────────
# The launcher polls this instead of /health so it can distinguish the
# release backend from any other process already on port 8000.
@app.get("/nexus-ready")
async def nexus_ready():
    from core.openclaw_process import _is_gateway_alive
    gw_ok = False
    try:
        gw_ok = _is_gateway_alive()
    except Exception:
        pass
    return {"status": "ok", "gateway": gw_ok, "version": "nexus-release-1.0"}


# ── Resolve static dir once at import time (no directory scan) ───────────────
_static_candidates = [
    os.environ.get("NEXUS_STATIC_DIR", ""),
    os.path.join(APP_DIR, "out"),
    os.path.join(base_path, "out"),
    os.path.join(base_path, "_internal", "out"),                   # PyInstaller 6+
    os.path.join(base_path, "frontend", "dist"),                   # spec destination
    os.path.join(base_path, "_internal", "frontend", "dist"),      # PyInstaller 6+ spec
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out"),
]
_static_dir: str | None = None
for _c in _static_candidates:
    if _c and os.path.isfile(os.path.join(_c, "index.html")):
        _static_dir = _c
        break

_API_PREFIXES = ("agent", "tools", "openclaw", "events", "health",
                 "settings", "system", "voice", "openapi.json")

if _static_dir:
    # ── Serve SPA — FileResponse only, no StaticFiles scanner (faster) ────────
    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse(os.path.join(_static_dir, "index.html"))

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        # Let API routes through
        if full_path.split("/")[0] in _API_PREFIXES:
            from fastapi import HTTPException
            raise HTTPException(status_code=404)
        # Exact static file
        fp = os.path.join(_static_dir, full_path)
        if os.path.isfile(fp):
            return FileResponse(fp)
        # Next.js trailing-slash index
        ip = os.path.join(_static_dir, full_path, "index.html")
        if os.path.isfile(ip):
            return FileResponse(ip)
        # SPA fallback
        return FileResponse(os.path.join(_static_dir, "index.html"))


def main():
    if "--install-playwright" in sys.argv:
        try:
            print("Installing Playwright browsers...")
            from playwright.__main__ import main as playwright_main
            sys.argv = ["playwright", "install", "chromium"]
            playwright_main()
            sys.exit(0)
        except Exception as e:
            print(f"Failed to install Playwright browsers: {e}")
            sys.exit(1)

    import uvicorn
    try:
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8000,
            log_level="warning",
            use_colors=False,
            access_log=False,      # skip per-request logging — faster
            loop="asyncio",
        )
    except Exception as e:
        import traceback, datetime
        _fatal = os.path.join(APP_DIR, "nexus_fatal.log")
        with open(_fatal, "a") as f:
            f.write(f"\n[{datetime.datetime.now()}] FATAL: {e}\n{traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main()
