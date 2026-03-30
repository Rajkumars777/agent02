# -*- mode: python ; coding: utf-8 -*-
"""
NEXUS.spec — PyInstaller build spec for NEXUS Desktop Application
Run with:  pyinstaller NEXUS.spec
"""

import os
import sys

ROOT = os.path.abspath(SPECPATH)
BACKEND_DIR = os.path.join(ROOT, "backend")
STATIC_DIR = os.path.join(ROOT, "out")  # Next.js static export

# ── Collect all data files ─────────────────────────────────────────────────────
datas = []

# 1. Next.js static build (entire out/ folder)
if os.path.isdir(STATIC_DIR):
    datas.append((STATIC_DIR, "out"))
else:
    print("WARNING: out/ not found — run 'npm run build' first!")

# 2. Backend config template
config_src = os.path.join(BACKEND_DIR, "config.json")
if os.path.exists(config_src):
    datas.append((config_src, "."))

# 3. API routers
datas.append((os.path.join(BACKEND_DIR, "api"), "api"))

# 4. Core modules
datas.append((os.path.join(BACKEND_DIR, "core"), "core"))

# 5. Capabilities
caps_dir = os.path.join(BACKEND_DIR, "capabilities")
if os.path.isdir(caps_dir):
    datas.append((caps_dir, "capabilities"))

# 6. Bundled Node.js environment
node_dir = os.path.join(ROOT, "bin", "node")
if os.path.exists(node_dir):
    datas.append((node_dir, os.path.join("bin", "node")))


# ── Hidden imports needed by FastAPI / dependencies ───────────────────────────
hiddenimports = [
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "fastapi",
    "fastapi.staticfiles",
    "fastapi.responses",
    "starlette.staticfiles",
    "starlette.responses",
    "anyio",
    "anyio._backends._asyncio",
    "asyncio",
    "email.mime.text",
    "email.mime.multipart",
    "multipart",
    "python_multipart",
    "psutil",
    "requests",
    "httpx",
    "openai",
    "dotenv",
    "pandas",
    "openpyxl",
    "docx",
    "pptx",
    "reportlab",
    "PyPDF2",
    "yfinance",
    "websocket",
    "tkinter",
    "tkinter.ttk",
    "tkinter.messagebox",
    # Backend modules
    "api.routers.agent",
    "api.routers.events",
    "api.routers.settings",
    "api.routers.openclaw",
    "api.routers.tools",
    "core.agent",
    "core.memory",
]

# Optional: pystray for tray icon
try:
    import pystray
    hiddenimports += ["pystray", "PIL", "PIL.Image", "PIL.ImageDraw"]
except ImportError:
    pass

a = Analysis(
    [os.path.join(BACKEND_DIR, "nexus_launcher.py")],
    pathex=[BACKEND_DIR, ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib", "scipy", "sklearn", "torch", "tensorflow",
        "notebook", "jupyter", "IPython",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="NEXUS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # No console window (--noconsole)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # Add your .ico file path here if you have one
)
