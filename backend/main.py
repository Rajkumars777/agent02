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

# ── PyInstaller path setup ────────────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    _base = sys._MEIPASS
    _exe  = os.path.dirname(sys.executable)
    if _exe not in sys.path:
        sys.path.insert(0, _exe)
else:
    _base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if _base not in sys.path:
    sys.path.insert(0, _base)

base_path = _base

# ── Config path (injected by nexus_launcher before uvicorn starts) ────────────
APP_DIR = os.path.join(os.path.expanduser("~"), "AppData", "Local", "NEXUS")
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

# ── FastAPI app (routers registered lazily in lifespan) ──────────────────────
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Import routers HERE so their heavy dependencies load after uvicorn
    # is already listening — this is what makes the /health probe return fast.
    from api.routers import agent    as agent_router
    from api.routers import events   as events_router
    from api.routers import settings as settings_router
    from api.routers import openclaw as openclaw_router
    from api.routers import tools    as tools_router
    from api.routers import system   as system_router
    from api.routers import voice    as voice_router

    app.include_router(agent_router.router)
    app.include_router(events_router.router)
    app.include_router(settings_router.router)
    app.include_router(openclaw_router.router)
    app.include_router(tools_router.router)
    app.include_router(system_router.router)
    app.include_router(voice_router.router)

    logger.warning("NEXUS backend ready.")
    yield
    logger.warning("NEXUS backend shutting down.")

app = FastAPI(lifespan=lifespan, title="NEXUS Agent Backend", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── /health — responds immediately (before routers finish loading) ─────────────
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# ── Resolve static dir once at import time (no directory scan) ───────────────
_static_candidates = [
    os.environ.get("NEXUS_STATIC_DIR", ""),
    os.path.join(APP_DIR, "out"),
    os.path.join(base_path, "out"),
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
