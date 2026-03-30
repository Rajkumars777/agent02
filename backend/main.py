import sys
import os
import logging
from dotenv import load_dotenv

# Redirect stdout/stderr if None (happens with PyInstaller --noconsole)
class NullStream:
    def write(self, data): pass
    def flush(self): pass
    def isatty(self): return False
    def __getattr__(self, name): return None

if sys.stdout is None: sys.stdout = NullStream()
if sys.stderr is None: sys.stderr = NullStream()

load_dotenv()

# ── PyInstaller path setup ────────────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
    exe_dir = os.path.dirname(sys.executable)
    if exe_dir not in sys.path:
        sys.path.insert(0, exe_dir)
else:
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if base_path not in sys.path:
    sys.path.insert(0, base_path)

# ── When running as packaged .exe, load config from APP_DIR ──────────────────
APP_DIR = os.path.join(os.path.expanduser("~"), "AppData", "Local", "NEXUS")
custom_config = os.environ.get("NEXUS_CONFIG_PATH", os.path.join(APP_DIR, "config.json"))
if os.path.exists(custom_config):
    # Make it available to the rest of the backend
    os.environ.setdefault("NEXUS_CONFIG_PATH", custom_config)

from fastapi import FastAPI
from contextlib import asynccontextmanager
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api.routers import agent as agent_router
from api.routers import events as events_router
from api.routers import settings as settings_router
from api.routers import openclaw as openclaw_router
from api.routers import tools as tools_router

# Configure logging
log_file = os.path.join(os.path.expanduser("~"), "nexus_backend.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Startup: AI Engine Ready")
    yield
    logger.info("Shutdown: Closing connections...")

app = FastAPI(lifespan=lifespan, title="AI Agent Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount API routers first (higher priority than static) ─────────────────────
app.include_router(agent_router.router)
app.include_router(events_router.router)
app.include_router(settings_router.router)
app.include_router(openclaw_router.router)
app.include_router(tools_router.router)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# ── Serve the Next.js static build (if available) ─────────────────────────────
# Priority: NEXUS_STATIC_DIR env var > APP_DIR/out > SRC_DIR/out
_static_candidates = [
    os.environ.get("NEXUS_STATIC_DIR", ""),
    os.path.join(APP_DIR, "out"),
    os.path.join(base_path, "out"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out"),
]

_static_dir = None
for _candidate in _static_candidates:
    if _candidate and os.path.isdir(_candidate) and os.path.exists(os.path.join(_candidate, "index.html")):
        _static_dir = _candidate
        break

if _static_dir:
    logger.info(f"Serving Next.js static files from: {_static_dir}")
    app.mount("/static-assets", StaticFiles(directory=_static_dir), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse(os.path.join(_static_dir, "index.html"))

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """Serve the SPA — first try to serve the exact file, fallback to index.html."""
        # Don't intercept API routes
        if full_path.startswith(("agent/", "tools/", "openclaw/", "events/", "health", "docs", "openapi")):
            from fastapi import HTTPException
            raise HTTPException(status_code=404)
        
        # Try exact file
        file_path = os.path.join(_static_dir, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        
        # Try with trailing slash (Next.js static export style)
        index_path = os.path.join(_static_dir, full_path, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)
        
        # Fallback to root index
        return FileResponse(os.path.join(_static_dir, "index.html"))
else:
    logger.info("No static frontend found — serving API only (development mode).")


def main():
    try:
        logger.info("Starting Uvicorn backend on 127.0.0.1:8000")
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8000,
            log_level="info",
            use_colors=False
        )
    except Exception as e:
        with open(os.path.join(os.path.expanduser("~"), "nexus_fatal.log"), "a") as f:
            import traceback
            import datetime
            f.write(f"\n[{datetime.datetime.now()}] FATAL: {str(e)}\n")
            f.write(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
