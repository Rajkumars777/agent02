import sys
import os
import subprocess
import threading
import json
import logging
import time
import shutil

logger = logging.getLogger(__name__)

# ─── Path Resolution ───────────────────────────────────────────────────────────
#
#   FROZEN (PyInstaller --onefile):
#     _MEIPASS_DIR  → temp dir with extracted Python packages + bundled assets
#     _EXE_DIR      → folder containing ai-engine.exe  (dist/)
#
#   DEV (plain Python):
#     _MEIPASS_DIR  → src/core/  (where this file lives)
#     _EXE_DIR      → project root  (AI-agent---LTID-main/)
#

if getattr(sys, 'frozen', False):
    _MEIPASS_DIR = sys._MEIPASS
    _EXE_DIR     = os.path.dirname(os.path.abspath(sys.executable))
else:
    _MEIPASS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # src/
    _EXE_DIR     = os.path.dirname(_MEIPASS_DIR)                                # project root


def _get_openclaw_home() -> str:
    """
    Return path to the .openclaw config/session directory.

    Priority:
      1. OPENCLAW_HOME environment variable  (CI / Docker override)
      2. .openclaw/ next to the .exe         (portable frozen build)
      3. .openclaw/ inside _MEIPASS          (bundled by spec file)
      4. .openclaw/ at project root          (dev mode)
      5. ~/.openclaw                          (system default fallback)
    """
    # 1. Explicit env override
    if env_home := os.environ.get("OPENCLAW_HOME"):
        logger.info(f"OPENCLAW_HOME from env: {env_home}")
        return env_home

    # 2. Next to the .exe (portable frozen build)
    exe_home = os.path.join(_EXE_DIR, ".openclaw")
    if os.path.exists(exe_home):
        logger.info(f"Using .openclaw next to exe: {exe_home}")
        return exe_home

    # 3. System default (preferred for installed frozen builds to ensure persistence)
    system_home = os.path.join(os.path.expanduser("~"), ".openclaw")
    if getattr(sys, 'frozen', False):
        # In a bundle, we want persistence. Check system home first.
        if os.path.exists(system_home) or not os.path.exists(os.path.join(_MEIPASS_DIR, ".openclaw")):
             logger.info(f"Using system .openclaw for persistent bundle storage: {system_home}")
             return system_home

    # 4. Bundled inside _MEIPASS (frozen, spec file puts it here as a fallback)
    meipass_home = os.path.join(_MEIPASS_DIR, ".openclaw")
    if os.path.exists(meipass_home):
        logger.info(f"Using bundled .openclaw in _MEIPASS: {meipass_home}")
        return meipass_home

    # 5. Project root — dev mode
    project_home = os.path.join(_EXE_DIR, ".openclaw")
    if os.path.exists(project_home):
        logger.info(f"Using project-root .openclaw: {project_home}")
        return project_home

    # Default fallback
    logger.info(f"Falling back to system .openclaw: {system_home}")
    return system_home


def _get_node_executable() -> str:
    """
    Return path to node.exe.

    Priority:
      1. bin/node.exe next to the .exe
      2. bin/node.exe inside _MEIPASS  (spec bundles it here)
      3. bin/node.exe at project root  (dev)
      4. 'node' from PATH              (system install)
    """
    ext = ".exe" if os.name == "nt" else ""

    candidates = [
        os.path.join(_EXE_DIR,     "bin", f"node{ext}"),
        os.path.join(_MEIPASS_DIR, "bin", f"node{ext}"),
        os.path.join(_EXE_DIR,     f"node{ext}"),
    ]

    for path in candidates:
        if os.path.exists(path):
            logger.info(f"Using node: {path}")
            return path

    # Fall back to system node
    logger.info("Using system node from PATH")
    return f"node{ext}"


def _get_openclaw_script() -> str:
    """
    Return path to openclaw.mjs.

    Priority:
      1. openclaw/openclaw.mjs inside _MEIPASS   (spec bundles it as 'openclaw/')
      2. openclaw/openclaw.mjs next to the .exe
      3. node_modules/openclaw/openclaw.mjs at project root  (dev)
      4. frontend/node_modules/openclaw/openclaw.mjs         (dev alternate)
    """
    candidates = [
        # Frozen (spec: destination='openclaw')
        os.path.join(_MEIPASS_DIR, "openclaw", "openclaw.mjs"),
        # Next to .exe
        os.path.join(_EXE_DIR, "openclaw", "openclaw.mjs"),
        # Dev: project root node_modules
        os.path.join(_EXE_DIR, "node_modules", "openclaw", "openclaw.mjs"),
        # Dev: frontend node_modules
        os.path.join(_EXE_DIR, "frontend", "node_modules", "openclaw", "openclaw.mjs"),
    ]

    for path in candidates:
        if os.path.exists(path):
            logger.info(f"Using openclaw script: {path}")
            return path

    logger.warning("openclaw.mjs not found in any expected location")
    return candidates[0]  # Return first candidate so error message is useful


def _resolve_openclaw_command() -> list[str]:
    """
    Build the argv list for running openclaw.

    Priority:
      1. Bundled node + bundled openclaw.mjs  (fully self-contained)
      2. Global 'openclaw' binary             (user has it installed)
      3. Local node_modules/.bin/openclaw     (project-local install)
      4. npx openclaw                         (auto-download, slowest)
      5. Raise RuntimeError with instructions
    """
    node_exe    = _get_node_executable()
    script_path = _get_openclaw_script()

    # 1. Bundled node + bundled script (best — no external dependencies)
    if os.path.exists(node_exe) and os.path.exists(script_path):
        logger.info("Using bundled node + openclaw.mjs")
        return [node_exe, script_path]

    # 2. Global openclaw binary
    if shutil.which("openclaw"):
        logger.info("Using global openclaw binary")
        return ["openclaw"]

    # 3. Project-local node_modules/.bin/openclaw
    local_bin_win  = os.path.join(_EXE_DIR, "node_modules", ".bin", "openclaw.cmd")
    local_bin_unix = os.path.join(_EXE_DIR, "node_modules", ".bin", "openclaw")
    for local_bin in [local_bin_win, local_bin_unix]:
        if os.path.exists(local_bin):
            logger.info(f"Using local openclaw: {local_bin}")
            return [local_bin]

    # 4. npx fallback (version-pinned to avoid surprises)
    if shutil.which("node"):
        logger.warning("Falling back to npx openclaw (first run may be slow)")
        return ["npx", "openclaw@latest"]

    # 5. Nothing found — give the user clear instructions
    raise RuntimeError(
        "OpenClaw not found. Fix options:\n"
        "  Option A (recommended): npm install -g openclaw\n"
        "  Option B (project-local): npm install openclaw   (inside frontend/)\n"
        "  Option C: Install Node.js from https://nodejs.org  (enables npx fallback)\n"
        f"  Option D: Place node.exe in {os.path.join(_EXE_DIR, 'bin')}\\"
    )


# ─── State ─────────────────────────────────────────────────────────────────────

_process:      subprocess.Popen | None = None
_gateway_port: int                     = 18789
_gateway_log:  list[str]               = []
_qr_data:      str | None              = None
_status:       str                     = "stopped"   # stopped | starting | running | error

MAX_LOG_LINES = 200


def _get_config() -> dict:
    config_path = os.path.join(_get_openclaw_home(), "openclaw.json")
    try:
        if not os.path.exists(config_path):
            return {}
        with open(config_path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _is_gateway_alive(port: int | None = None) -> bool:
    """Check if the OpenClaw gateway is responding on the given port."""
    import urllib.request
    p = port or _gateway_port
    try:
        # Probe the root or dashboard endpoint
        req = urllib.request.urlopen(
            f"http://127.0.0.1:{p}/", timeout=2
        )
        return req.status < 500
    except Exception:
        return False


def _reader_thread(pipe, label: str):
    """Read process stdout/stderr, capture QR codes and status lines."""
    global _qr_data, _status
    try:
        for raw_line in iter(pipe.readline, ""):
            line = raw_line.strip()
            if not line:
                continue

            _gateway_log.append(f"[{label}] {line}")
            if len(_gateway_log) > MAX_LOG_LINES:
                _gateway_log.pop(0)

            if line.startswith("data:image/") or "base64," in line:
                _qr_data = line
                logger.info("[OpenClaw] Captured QR code data")

            low = line.lower()
            if "gateway" in low and ("ready" in low or "listening" in low or "started" in low):
                _status = "running"
                logger.info(f"[OpenClaw] Gateway running on port {_gateway_port}")

            if "error" in low:
                logger.warning(f"[OpenClaw] {line}")

    except Exception as e:
        logger.error(f"[OpenClaw reader] {e}")


# ─── Public API ────────────────────────────────────────────────────────────────

def start_gateway(port: int | None = None) -> dict:
    """Start the OpenClaw gateway process."""
    global _process, _gateway_port, _status, _gateway_log, _qr_data

    config        = _get_config()
    _gateway_port = port or config.get("gateway", {}).get("port", 18789)

    # Already alive (external process or ours)
    if _is_gateway_alive(_gateway_port):
        _status = "running"
        msg = f"Gateway already running on port {_gateway_port}"
        _gateway_log.append(f"[NEXUS] {msg}")
        return {"success": True, "message": msg, "status": "running", "port": _gateway_port}

    # Our process still alive
    if _process and _process.poll() is None:
        return {"success": True, "message": "Gateway process already running",
                "status": _status, "port": _gateway_port}

    _status = "starting"
    _gateway_log.clear()
    _qr_data = None

    openclaw_home = _get_openclaw_home()

    # Set up log files inside .openclaw/logs/
    log_dir     = os.path.join(openclaw_home, "logs")
    os.makedirs(log_dir, exist_ok=True)
    stdout_path = os.path.join(log_dir, "gateway-stdout.log")
    stderr_path = os.path.join(log_dir, "gateway-stderr.log")

    try:
        argv = _resolve_openclaw_command()
    except RuntimeError as e:
        _status = "error"
        return {"success": False, "message": str(e), "status": _status}

    # Full command: <argv> gateway run --port 18789 --allow-unconfigured
    argv = _resolve_openclaw_command()
    cmd = argv + ["gateway", "run", "--port", str(_gateway_port), "--allow-unconfigured"]

    logger.info(f"[OpenClaw] Command : {' '.join(cmd)}")
    logger.info(f"[OpenClaw] Home    : {openclaw_home}")
    _gateway_log.append(f"[NEXUS] Starting: {' '.join(cmd)}")

    env                  = os.environ.copy()
    env["OPENCLAW_HOME"] = openclaw_home
    env["HOME"]          = os.path.dirname(openclaw_home)
    env["USERPROFILE"]   = os.path.dirname(openclaw_home)

    creation_flags = 0
    if os.name == "nt":
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

    stdout_log = open(stdout_path, "a", encoding="utf-8")
    stderr_log = open(stderr_path, "a", encoding="utf-8")

    try:
        _process = subprocess.Popen(
            cmd,
            shell=False,          # never shell=True with a list — use shell=True only with a plain string
            stdout=stdout_log,
            stderr=stderr_log,
            creationflags=creation_flags,
            text=True,
            env=env,
        )
    except FileNotFoundError:
        _status = "error"
        stdout_log.close()
        stderr_log.close()
        return {
            "success": False,
            "message": (
                f"'{cmd[0]}' not found. "
                "Install openclaw globally: npm install -g openclaw"
            ),
            "status": _status,
        }
    except Exception as e:
        _status = "error"
        try: stdout_log.close()
        except: pass
        try: stderr_log.close()
        except: pass
        return {"success": False, "message": str(e), "status": _status}

    # ── Poll until gateway is live (up to 3 seconds in dev) ──────────────────────────
    max_retries = 3 if os.environ.get("OPENCLAW_FAST_START") else 20
    try:
        for i in range(max_retries):
            time.sleep(1)

            if _is_gateway_alive(_gateway_port):
                _status = "running"
                _gateway_log.append(f"[NEXUS] ✅ Gateway live on port {_gateway_port}")
                logger.info(f"[OpenClaw] Gateway live on port {_gateway_port}")
                return {
                    "success": True,
                    "message": f"Gateway started on port {_gateway_port}",
                    "status":  "running",
                    "port":    _gateway_port,
                }

            if _process.poll() is not None:
                # Process died — read the last 500 chars from stderr log
                stdout_log.flush()
                stderr_log.flush()
                try:
                    with open(stderr_path, "r", encoding="utf-8") as f:
                        err = f.read().strip()[-500:]
                except Exception:
                    err = "unknown error"
                _status = "error"
                _gateway_log.append(f"[NEXUS] ❌ Gateway exited: {err}")
                return {"success": False, "message": f"Gateway exited early:\n{err}", "status": _status}

        # 20 s elapsed — process alive but port not responding
        _status = "starting"
        _gateway_log.append("[NEXUS] ⚠ Gateway process running, port not ready yet")
        return {
            "success": True,
            "message": f"Gateway process started (PID {_process.pid}), waiting for port...",
            "status":  "starting",
            "port":    _gateway_port,
        }

    finally:
        # Always release file handles
        try: stdout_log.close()
        except Exception: pass
        try: stderr_log.close()
        except Exception: pass


def stop_gateway() -> dict:
    """Stop the OpenClaw gateway process."""
    global _process, _status

    if _process and _process.poll() is None:
        _process.terminate()
        try:
            _process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _process.kill()
        _status = "stopped"
        _gateway_log.append("[NEXUS] Gateway stopped")
        return {"success": True, "message": "Gateway stopped"}

    _status = "stopped"
    return {"success": True, "message": "Gateway was not running"}


def get_status() -> dict:
    """Return current gateway status, probing the port to detect external gateways."""
    global _status

    if _is_gateway_alive():
        _status = "running"
    elif _process and _process.poll() is None:
        _status = "starting"   # process alive, port not ready yet
    else:
        _status = "stopped"

    config          = _get_config()
    gateway_config  = config.get("gateway", {})
    channels_config = config.get("channels", {})

    channels_status = {}
    for name, cfg in channels_config.items():
        channels_status[name] = {**cfg, "has_token": bool(cfg.get("token"))}

    # WhatsApp pairing check — credentials folder exists and is non-empty
    wa_creds = os.path.join(_get_openclaw_home(), "credentials", "whatsapp")
    if os.path.isdir(wa_creds) and any(os.listdir(wa_creds)):
        channels_status.setdefault("whatsapp", {})["paired"] = True

    raw_model  = config.get("agents", {}).get("defaults", {}).get("model", "unknown")
    model_name = raw_model.get("primary", "unknown") if isinstance(raw_model, dict) else str(raw_model)

    return {
        "status":             _status,
        "port":               _gateway_port,
        "pid":                _process.pid if _process and _process.poll() is None else None,
        "qr_data":            _qr_data,
        "log_tail":           _gateway_log[-20:],
        "gateway_auth_token": gateway_config.get("auth", {}).get("token", ""),
        "channels":           channels_status,
        "model":              model_name,
    }


def start_channel_pairing(channel: str = "whatsapp") -> dict:
    """Trigger channel pairing (produces a QR code for WhatsApp)."""
    global _qr_data
    _qr_data = None

    openclaw_home = _get_openclaw_home()
    argv          = _resolve_openclaw_command()

    config = _get_config()
    if channel == "whatsapp":
        cmd = argv + ["channels", "login", "--channel", channel]
    else:
        token = config.get("channels", {}).get(channel, {}).get("token")
        cmd   = argv + ["channels", "add", "--channel", channel]
        if token:
            cmd += ["--token", token]

    logger.info(f"[OpenClaw] Pairing: {' '.join(cmd)}")

    env                  = os.environ.copy()
    env["OPENCLAW_HOME"] = os.path.dirname(openclaw_home)
    env["HOME"]          = os.path.dirname(openclaw_home)
    env["USERPROFILE"]   = os.path.dirname(openclaw_home)

    def _pair_reader():
        global _qr_data
        try:
            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
            proc = subprocess.Popen(
                cmd, shell=False,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, env=env,
                creationflags=creation_flags,
            )
            if proc.stdout:
                for line in iter(proc.stdout.readline, ""):
                    line = line.strip()
                    if not line:
                        continue
                    _gateway_log.append(f"[Pairing] {line}")
                    if len(_gateway_log) > MAX_LOG_LINES:
                        _gateway_log.pop(0)
                    if line.startswith("data:image/") or "base64," in line:
                        _qr_data = line
                        logger.info("[OpenClaw] QR code captured from pairing process")
                    if "Linked!" in line or "Ready" in line:
                        logger.info("[OpenClaw] Channel linked")
            proc.wait(timeout=10)
        except Exception as e:
            logger.error(f"[OpenClaw pairing] {e}")

    threading.Thread(target=_pair_reader, daemon=True).start()
    return {
        "success": True,
        "message": f"Pairing started for {channel}. Check status in a few seconds.",
        "qr_data": _qr_data,
    }


def logout_channel(channel: str = "whatsapp") -> dict:
    """Log out of a messaging channel."""
    global _qr_data

    openclaw_home = _get_openclaw_home()
    argv          = _resolve_openclaw_command()
    cmd           = argv + ["channels", "logout", "--channel", channel]

    logger.info(f"[OpenClaw] Logout: {' '.join(cmd)}")

    env                  = os.environ.copy()
    env["OPENCLAW_HOME"] = os.path.dirname(openclaw_home)
    env["HOME"]          = os.path.dirname(openclaw_home)
    env["USERPROFILE"]   = os.path.dirname(openclaw_home)

    try:
        result = subprocess.run(
            cmd, shell=False,
            capture_output=True, text=True,
            env=env, timeout=30,
        )
        output = (result.stdout + "\n" + result.stderr).strip()
        _gateway_log.append(f"[NEXUS] Logout: {output[:500]}")
        _qr_data = None
        return {
            "success": result.returncode == 0,
            "message": "Logged out successfully" if result.returncode == 0
                       else f"Logout failed: {output[:200]}",
            "output":  output,
        }
    except Exception as e:
        return {"success": False, "message": str(e)}
