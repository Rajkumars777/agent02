# -*- mode: python ; coding: utf-8 -*-
"""
nexus_launcher.spec
===================
PyInstaller spec for the NEXUS portable launcher.

Produces:  dist/NEXUS/NEXUS.exe
           dist/NEXUS/_internal/   ← all runtime deps, bundled frontend, node.exe, openclaw

Run:  pyinstaller nexus_launcher.spec --clean
"""

import os
import sys
from PyInstaller.utils.hooks import (
    collect_data_files, collect_submodules, collect_dynamic_libs
)

block_cipher = None

# ── Paths ──────────────────────────────────────────────────────────────────────
SPEC_DIR   = os.path.dirname(os.path.abspath(SPEC))   # project root (Agent02/)
BACKEND    = os.path.join(SPEC_DIR, "backend")
OUT_DIR    = os.path.join(SPEC_DIR, "out")            # Next.js static export
NODE_DIR   = os.path.join(SPEC_DIR, "bin", "node")    # bundled node.exe

# ── Data files ────────────────────────────────────────────────────────────────
datas = []

# 1. Next.js static export → served as /  by FastAPI
if os.path.isdir(OUT_DIR):
    datas += [(OUT_DIR, "out")]
    print(f"[spec] Bundling static frontend: {OUT_DIR}")
else:
    print(f"[spec] WARNING: out/ not found at {OUT_DIR}. Run 'npm run build' first.")

# 2. Bundled Node.js binary
if os.path.isdir(NODE_DIR):
    datas += [(NODE_DIR, os.path.join("bin", "node"))]
    print(f"[spec] Bundling Node.js: {NODE_DIR}")
else:
    print(f"[spec] WARNING: bin/node/ not found. Gateway auto-install will use npm from PATH.")

# 3. Bundle openclaw package if installed in local node_modules
#    We only bundle the dist/ and top-level files (NOT node_modules) because
#    openclaw's node_modules contains platform-specific native binaries (.node)
#    compiled on the build machine — they will crash with ERR_MODULE_NOT_FOUND
#    on any other PC.  The runtime auto-installer handles first-run setup.
_openclaw_candidates = [
    os.path.join(SPEC_DIR,   "node_modules", "openclaw"),
    os.path.join(SPEC_DIR,   "frontend", "node_modules", "openclaw"),
    os.path.join(NODE_DIR,   "node_modules", "openclaw"),
    os.path.join(SPEC_DIR,   "bin", "node", "node_modules", "openclaw"),
]
_openclaw_bundled = False
for _oc_src in _openclaw_candidates:
    _oc_mjs = os.path.join(_oc_src, "openclaw.mjs")
    if os.path.isfile(_oc_mjs):
        # Bundle only the files needed to run: openclaw.mjs, dist/, package.json, assets/
        # SKIP node_modules — native binaries are machine-specific!
        for _sub in ["", "dist", "assets", "skills", "scripts"]:
            _sub_path = os.path.join(_oc_src, _sub) if _sub else _oc_src
            if _sub == "":
                # top-level files only
                for _f in ["openclaw.mjs", "package.json"]:
                    _fp = os.path.join(_oc_src, _f)
                    if os.path.isfile(_fp):
                        datas += [(_fp, "openclaw")]
            elif os.path.isdir(_sub_path):
                datas += [(_sub_path, os.path.join("openclaw", _sub))]
        print(f"[spec] Bundling openclaw (no node_modules) from: {_oc_src}")
        _openclaw_bundled = True
        break
if not _openclaw_bundled:
    print("[spec] WARNING: openclaw package not found locally.")
    print("[spec]   Run:  npm install openclaw  (in project root or frontend/)")
    print("[spec]   NEXUS will auto-install openclaw on first run via bundled npm.")

# 4. Backend source tree (all Python modules)
backend_src_entries = [
    ("api",          "backend/api"),
    ("core",         "backend/core"),
    ("capabilities", "backend/capabilities"),
]
for src_relative, dest in backend_src_entries:
    src_abs = os.path.join(BACKEND, src_relative.split("/")[-1])
    if os.path.isdir(src_abs):
        datas += [(src_abs, dest)]

# backend config.json (blank template — user fills API key)
_bcfg = os.path.join(BACKEND, "config.json")
if os.path.exists(_bcfg):
    datas += [(_bcfg, ".")]

# 5. Python package data files
for pkg in ["uvicorn", "starlette", "certifi", "httpx"]:
    try:
        datas += collect_data_files(pkg)
    except Exception:
        pass

for pkg in ["langchain", "langchain_core", "langchain_openai", "langchain_google_genai"]:
    try:
        datas += collect_data_files(pkg)
    except Exception:
        pass

for pkg in ["reportlab", "docx", "pptx", "faster_whisper", "ctranslate2"]:
    try:
        if pkg == "tiktoken":
            datas += collect_data_files(pkg, includes=["*.tiktoken"])
        else:
            datas += collect_data_files(pkg)
    except Exception:
        pass

try:
    datas += collect_data_files("tiktoken", includes=["*.tiktoken"])
except Exception:
    pass

# ── Dynamic libraries ──────────────────────────────────────────────────────────
binaries = []
for pkg in ["ctranslate2", "av"]:
    try:
        binaries += collect_dynamic_libs(pkg)
    except Exception:
        pass

# ── Hidden imports ─────────────────────────────────────────────────────────────
hiddenimports = [
    # FastAPI / uvicorn internals
    "uvicorn.logging", "uvicorn.loops", "uvicorn.loops.asyncio",
    "uvicorn.protocols", "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto", "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan", "uvicorn.lifespan.on",
    "starlette.routing", "starlette.middleware", "starlette.middleware.cors",
    # pydantic
    "pydantic", "pydantic.v1",
    # OpenAI / LangChain
    "openai", "langchain", "langchain_core", "langchain_openai",
    "langchain_google_genai",
    # Google auth
    "google.auth", "google.auth.transport", "google.oauth2", "google.api_core",
    # async
    "asyncio", "anyio", "anyio._backends._asyncio", "anyio._backends._trio",
    # backend routers
    "api.routers.agent", "api.routers.events", "api.routers.settings",
    "api.routers.openclaw", "api.routers.tools", "api.routers.system",
    "api.routers.voice",
    # core
    "core.agent", "core.memory", "core.openclaw_client", "core.openclaw_process",
    # voice
    "faster_whisper", "ctranslate2",
    # file handling
    "docx", "pptx", "reportlab", "PyPDF2", "openpyxl", "pandas", "yfinance",
    # browser automation
    "playwright", "playwright.async_api", "playwright.sync_api", "browser_use",
    # HTTP
    "httpx", "aiohttp", "requests",
    # crypto
    "cryptography", "cryptography.fernet",
    # system
    "psutil", "winreg",
    # tray
    "pystray", "PIL", "PIL.Image", "PIL.ImageDraw",
    # audio
    "av", "av.audio", "av.video",
    # multipart
    "multipart", "python_multipart",
    # misc
    "websocket", "dotenv", "python_dotenv",
    # AppOpener
    "AppOpener",
] + collect_submodules("uvicorn") + collect_submodules("starlette")

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    ["nexus_launcher.py"],
    pathex=[SPEC_DIR, BACKEND],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch", "torchvision", "easyocr",
        "tkinter", "matplotlib", "notebook",
        "_pytest", "pytest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="NEXUS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=["vcruntime140.dll", "msvcp140.dll"],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=["vcruntime140.dll", "msvcp140.dll"],
    name="NEXUS",
)
