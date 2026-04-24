# -*- mode: python ; coding: utf-8 -*-
"""
nexus_backend.spec
==================
PyInstaller spec for the NEXUS backend (--onedir, faster cold start).
Bundles ALL Python packages and the Next.js static output.
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs

block_cipher = None

# ── Paths (resolved relative to this spec file = backend/) ────────────────────
SPEC_DIR     = os.path.dirname(os.path.abspath(SPEC))
PROJECT_ROOT = os.path.dirname(SPEC_DIR)          # Agent02/
OUT_DIR      = os.path.join(PROJECT_ROOT, 'out')  # Next.js static export

# ── Collect data files from key packages ──────────────────────────────────────
datas = []

# Next.js static export (served by FastAPI)
if os.path.isdir(OUT_DIR):
    datas += [(OUT_DIR, 'out')]

# uvicorn / starlette need their protocol implementations
datas += collect_data_files('uvicorn')
datas += collect_data_files('starlette')

# langchain / langchain_core data files
try:
    datas += collect_data_files('langchain')
    datas += collect_data_files('langchain_core')
    datas += collect_data_files('langchain_openai')
    datas += collect_data_files('langchain_google_genai')
except Exception:
    pass

# ctranslate2 needs its model data
try:
    datas += collect_data_files('ctranslate2')
except Exception:
    pass

# faster_whisper model files
try:
    datas += collect_data_files('faster_whisper')
except Exception:
    pass

# httpx / certifi certs
try:
    datas += collect_data_files('certifi')
    datas += collect_data_files('httpx')
except Exception:
    pass

# reportlab needs font data
try:
    datas += collect_data_files('reportlab')
except Exception:
    pass

# python-docx templates
try:
    datas += collect_data_files('docx')
except Exception:
    pass

# python-pptx templates
try:
    datas += collect_data_files('pptx')
except Exception:
    pass

# tiktoken encodings
try:
    datas += collect_data_files('tiktoken', includes=['*.tiktoken'])
except Exception:
    pass

# ── Dynamic libraries ──────────────────────────────────────────────────────────
binaries = []
try:
    binaries += collect_dynamic_libs('ctranslate2')
except Exception:
    pass
try:
    binaries += collect_dynamic_libs('av')
except Exception:
    pass

# ── Hidden imports ─────────────────────────────────────────────────────────────
hiddenimports = [
    # FastAPI / uvicorn internals
    'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.asyncio',
    'uvicorn.protocols', 'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan', 'uvicorn.lifespan.on',
    'starlette.routing', 'starlette.middleware', 'starlette.middleware.cors',
    # pydantic
    'pydantic', 'pydantic.v1',
    # OpenAI / LangChain
    'openai', 'langchain', 'langchain_core', 'langchain_openai',
    'langchain_google_genai',
    # Google auth
    'google.auth', 'google.auth.transport', 'google.oauth2',
    'google.api_core',
    # async
    'asyncio', 'anyio', 'anyio._backends._asyncio', 'anyio._backends._trio',
    # voice
    'faster_whisper', 'ctranslate2',
    # file handling
    'docx', 'pptx', 'reportlab', 'PyPDF2', 'openpyxl',
    'pandas', 'yfinance',
    # browser
    'playwright', 'playwright.async_api', 'playwright.sync_api',
    # HTTP
    'httpx', 'aiohttp', 'requests',
    # crypto
    'cryptography', 'cryptography.fernet',
    # system
    'psutil', 'winreg',
    # whisper audio
    'av', 'av.audio', 'av.video',
    # multipart
    'multipart', 'python_multipart',
    # misc
    'websocket', 'dotenv', 'python_dotenv',
] + collect_submodules('uvicorn') + collect_submodules('starlette')

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    ['main.py'],
    pathex=[SPEC_DIR, PROJECT_ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch', 'torchvision', 'easyocr',   # removed
        'tkinter', 'matplotlib', 'notebook',
        '_pytest', 'pytest',
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
    name='nexus_backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=['vcruntime140.dll', 'msvcp140.dll'],
    console=False,       # no terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=['vcruntime140.dll', 'msvcp140.dll'],
    name='nexus_backend',   # output folder: dist/nexus_backend/
)
