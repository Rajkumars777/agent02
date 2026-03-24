import sys
import os
import asyncio
import logging
from dotenv import load_dotenv

# Redirect stdout/stderr if None (happens with PyInstaller --noconsole)
# We use a more complete class to fool libraries that expect a real stream
class NullStream:
    def write(self, data): pass
    def flush(self): pass
    def isatty(self): return False
    def __getattr__(self, name): return None

if sys.stdout is None: sys.stdout = NullStream()
if sys.stderr is None: sys.stderr = NullStream()

load_dotenv()

# Configure path for PyInstaller ONEFILE
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
    # For onefile, we should also look in the directory of the executable
    exe_dir = os.path.dirname(sys.executable)
    if exe_dir not in sys.path:
        sys.path.insert(0, exe_dir)
else:
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if base_path not in sys.path:
    sys.path.insert(0, base_path)

from fastapi import FastAPI
from contextlib import asynccontextmanager
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

# Import Routers
try:
    from api.routers import agent as agent_router
    from api.routers import events as events_router
    from api.routers import settings as settings_router
    from api.routers import openclaw as openclaw_router
    from api.routers import tools as tools_router
except ImportError:
    # Fallback if bundled pathing is slightly off
    import api.routers.agent as agent_router
    import api.routers.events as events_router
    import api.routers.settings as settings_router
    import api.routers.openclaw as openclaw_router
    import api.routers.tools as tools_router

# Configure logging
log_file = os.path.join(os.path.expanduser("~"), "nexus_backend.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    os.environ["OPENCLAW_FAST_START"] = "1"
    logger.info("Startup: AI Engine Ready")
    try:
        try:
            from core.openclaw_process import start_gateway
        except ImportError:
            from core.openclaw_process import start_gateway
        if os.environ.get("OPENCLAW_FAST_START") != "1":
            start_gateway()
        else:
            logger.info("Skipping backend gateway start (FAST_START=1)")
        logger.info("OpenClaw Gateway started successfully")
    except Exception as e:
        logger.error(f"Failed to start OpenClaw Gateway: {e}")
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

app.include_router(agent_router.router)
app.include_router(events_router.router)
app.include_router(settings_router.router)
app.include_router(openclaw_router.router)
app.include_router(tools_router.router)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

def main():
    try:
        logger.info(f"Starting Uvicorn backend on 127.0.0.1:8000")
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8000,
            log_level="info",
            use_colors=False  # CRITICAL: Fixes isatty crash in --noconsole mode
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
