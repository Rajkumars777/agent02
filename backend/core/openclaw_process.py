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
if getattr(sys, 'frozen', False):
    _MEIPASS_DIR = sys._MEIPASS                                      # dist/NEXUS/_internal/
    _EXE_DIR     = os.path.dirname(os.path.abspath(sys.executable))  # dist/NEXUS/
else:
    _MEIPASS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _EXE_DIR     = os.path.dirname(_MEIPASS_DIR)

# ── AppData Path (persistent node / openclaw install) ─────────────────────────
_APP_DIR  = os.path.join(os.path.expanduser("~"), "AppData", "Local", "NEXUS")
_NODE_DIR = os.path.join(_APP_DIR, "node")   # npm-install target


# ─── Node executable ──────────────────────────────────────────────────────────
def _get_node_executable() -> str:
    ext = ".exe" if os.name == "nt" else ""
    candidates = [
        # AppData cached install
        os.path.join(_NODE_DIR, f"node{ext}"),
        # Bundled inside _internal/ (PyInstaller onedir)
        os.path.join(_MEIPASS_DIR, "bin", "node", f"node{ext}"),
        os.path.join(_EXE_DIR, "bin", "node", f"node{ext}"),
        os.path.join(_EXE_DIR, "_internal", "bin", "node", f"node{ext}"),
        os.path.join(_EXE_DIR, "bin", f"node{ext}"),
        os.path.join(_MEIPASS_DIR, "bin", f"node{ext}"),
        os.path.join(_EXE_DIR, f"node{ext}"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            logger.info(f"Using node: {path}")
            return path
    logger.info("Using system node from PATH")
    return f"node{ext}"


# ─── npm executable ───────────────────────────────────────────────────────────
def _get_npm_script() -> str | None:
    """Return path to npm.cmd (Windows) or npm script bundled with node."""
    node_exe = _get_node_executable()
    node_dir  = os.path.dirname(node_exe) if os.path.isfile(node_exe) else ""

    candidates = [
        os.path.join(node_dir, "npm.cmd"),
        os.path.join(node_dir, "npm"),
        shutil.which("npm") or "",
    ]
    for p in candidates:
        if p and os.path.isfile(p):
            return p
    return None


# ─── openclaw.mjs candidates ──────────────────────────────────────────────────
def _openclaw_candidates() -> list[str]:
    """Return ordered list of paths to try for openclaw.mjs.

    AppData (npm-installed, fresh native binaries for this machine) is tried
    FIRST so we don't accidentally use the bundled copy whose native modules
    were compiled on the build machine and will crash on any other PC.
    """
    return [
        # 1. AppData npm-installed (correct native binaries for this machine)
        os.path.join(_NODE_DIR, "lib", "node_modules", "openclaw", "openclaw.mjs"),
        os.path.join(_NODE_DIR, "node_modules", "openclaw", "openclaw.mjs"),
        os.path.join(_NODE_DIR, "openclaw.mjs"),
        # 2. Bundled in _internal/ — only used after validation check
        os.path.join(_MEIPASS_DIR, "openclaw", "openclaw.mjs"),
        os.path.join(_EXE_DIR, "_internal", "openclaw", "openclaw.mjs"),
        os.path.join(_EXE_DIR, "openclaw", "openclaw.mjs"),
        # 3. Dev node_modules
        os.path.join(_EXE_DIR, "node_modules", "openclaw", "openclaw.mjs"),
        os.path.join(_EXE_DIR, "frontend", "node_modules", "openclaw", "openclaw.mjs"),
    ]


def _get_openclaw_script() -> str:
    for path in _openclaw_candidates():
        if os.path.isfile(path):
            return path
    logger.warning("openclaw.mjs not found in any expected location")
    return _openclaw_candidates()[0]


# ─── Validate that a found openclaw.mjs actually runs (native deps OK) ────────
_validated_script: str | None = None  # cache of a working script path


def _validate_openclaw(script_path: str) -> bool:
    """Return True if node can import openclaw.mjs without ERR_MODULE_NOT_FOUND."""
    global _validated_script
    if _validated_script == script_path:
        return True

    node_exe = _get_node_executable()
    if not os.path.isfile(node_exe) and not shutil.which("node"):
        # Can't validate without node — assume it works and let runtime fail
        return True

    node_bin = node_exe if os.path.isfile(node_exe) else shutil.which("node")
    CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

    try:
        result = subprocess.run(
            [node_bin, "--input-type=module",
             "--eval", f'import "{script_path.replace(chr(92), "/")}"; process.exit(0);'],
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=CREATE_NO_WINDOW,
        )
        if result.returncode == 0:
            _validated_script = script_path
            logger.info(f"[OpenClaw] Validated: {script_path}")
            return True
        stderr = result.stderr or ""
        if "ERR_MODULE_NOT_FOUND" in stderr or "Cannot find" in stderr:
            logger.warning(f"[OpenClaw] Script failed validation (native deps broken): {script_path}")
            logger.warning(f"[OpenClaw] stderr: {stderr[:500]}")
            return False
        # Other error (e.g. missing config) — the file loaded OK, native deps fine
        _validated_script = script_path
        logger.info(f"[OpenClaw] Validated (non-zero but not module error): {script_path}")
        return True
    except subprocess.TimeoutExpired:
        # If it hung for 30 s it probably loaded — mark valid
        _validated_script = script_path
        return True
    except Exception as e:
        logger.warning(f"[OpenClaw] Validation exception: {e}")
        return False


def _find_working_openclaw() -> str | None:
    """Return the first openclaw.mjs path that passes validation."""
    for path in _openclaw_candidates():
        if os.path.isfile(path):
            if _validate_openclaw(path):
                return path
            logger.warning(f"[OpenClaw] Skipping broken script: {path}")
    return None


# ─── Auto-install openclaw via bundled npm ────────────────────────────────────
_install_lock   = threading.Lock()
_install_done   = False
_install_failed = False


def _ensure_openclaw() -> bool:
    """
    Ensure a *working* openclaw.mjs is available.
    If the bundled copy has broken native modules it will be skipped and
    openclaw will be npm-installed fresh into AppData/Local/NEXUS/node/.
    Returns True on success.
    """
    global _install_done, _install_failed

    # Quick path: already validated a working script
    if _find_working_openclaw():
        _install_done = True
        return True

    with _install_lock:
        if _install_done:
            return True
        if _install_failed:
            return False

        node_exe = _get_node_executable()
        has_node = os.path.isfile(node_exe) or bool(shutil.which("node"))
        if not has_node:
            logger.error("[OpenClaw] No node.exe found — cannot install openclaw")
            _install_failed = True
            return False

        npm_script = _get_npm_script()
        os.makedirs(_NODE_DIR, exist_ok=True)

        logger.warning("[OpenClaw] No working openclaw found — installing via npm…")
        _gateway_log.append("[NEXUS] Installing openclaw (first-run setup, ~30s)…")

        # Inject bundled node dir into PATH for npm's child processes
        node_dir = os.path.dirname(node_exe) if os.path.isfile(node_exe) else ""
        env = os.environ.copy()
        if node_dir and node_dir not in env.get("PATH", ""):
            env["PATH"] = node_dir + os.pathsep + env.get("PATH", "")

        CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

        if npm_script:
            cmd = [npm_script, "install", "-g", "openclaw",
                   "--prefix", _NODE_DIR, "--prefer-offline"]
        else:
            node_modules_npm = os.path.join(
                os.path.dirname(node_exe), "node_modules", "npm", "bin", "npm-cli.js"
            )
            if os.path.isfile(node_modules_npm):
                cmd = [node_exe, node_modules_npm, "install", "-g", "openclaw",
                       "--prefix", _NODE_DIR]
            else:
                logger.error("[OpenClaw] npm not found — cannot install openclaw")
                _install_failed = True
                return False

        log_path = os.path.join(_APP_DIR, "openclaw_install.log")
        try:
            with open(log_path, "a", encoding="utf-8") as lf:
                lf.write(f"\n--- install attempt {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                result = subprocess.run(
                    cmd,
                    stdout=lf, stderr=lf,
                    env=env,
                    timeout=300,
                    creationflags=CREATE_NO_WINDOW,
                )
        except subprocess.TimeoutExpired:
            logger.error("[OpenClaw] npm install timed out after 300 s")
            _install_failed = True
            return False
        except Exception as e:
            logger.error(f"[OpenClaw] npm install exception: {e}")
            _install_failed = True
            return False

        if result.returncode != 0:
            logger.error(f"[OpenClaw] npm install failed (rc={result.returncode}). See {log_path}")
            _install_failed = True
            return False

        # Verify it landed AND passes validation
        working = _find_working_openclaw()
        if working:
            logger.warning(f"[OpenClaw] openclaw installed and validated ✅: {working}")
            _install_done = True
            return True

        logger.error("[OpenClaw] npm reported success but no working openclaw found")
        _install_failed = True
        return False


# ─── Resolve the openclaw launch command ──────────────────────────────────────
def _resolve_openclaw_command() -> list[str]:
    """
    Build argv for openclaw. Tries (in order):
      1. AppData npm-installed (correct native binaries)
      2. Bundled (only if validated OK)
      3. Global 'openclaw' binary
      4. Local node_modules/.bin/openclaw
      5. npx openclaw@latest (slow first-run, needs internet)
      6. RuntimeError with instructions
    """
    node_exe    = _get_node_executable()
    script_path = _find_working_openclaw()

    # Inject bundled node into PATH
    if os.path.isfile(node_exe):
        node_dir = os.path.dirname(node_exe)
        if node_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = node_dir + os.pathsep + os.environ.get("PATH", "")
            logger.info(f"Injected bundled Node.js into PATH: {node_dir}")

    # 1. node + validated openclaw.mjs
    if script_path:
        node_bin = node_exe if os.path.isfile(node_exe) else shutil.which("node") or "node"
        logger.info(f"Using node + openclaw.mjs: {script_path}")
        return [node_bin, script_path]

    # 2. Global openclaw binary
    if shutil.which("openclaw"):
        logger.info("Using global openclaw binary")
        return ["openclaw"]

    # 3. Project-local node_modules/.bin/openclaw
    for local_bin in [
        os.path.join(_EXE_DIR, "node_modules", ".bin", "openclaw.cmd"),
        os.path.join(_EXE_DIR, "node_modules", ".bin", "openclaw"),
    ]:
        if os.path.isfile(local_bin):
            logger.info(f"Using local openclaw: {local_bin}")
            return [local_bin]

    # 4. npx fallback
    if shutil.which("node") or os.path.isfile(node_exe):
        logger.warning("Falling back to npx openclaw (first run may be slow)")
        npx = shutil.which("npx") or os.path.join(os.path.dirname(node_exe), "npx.cmd")
        if os.path.isfile(npx):
            return [npx, "--yes", "openclaw@latest"]
        return [node_exe, os.path.join(os.path.dirname(node_exe), "node_modules",
                                        "npm", "bin", "npx-cli.js"),
                "--yes", "openclaw@latest"]

    raise RuntimeError(
        "OpenClaw not found. Fix options:\n"
        "  Option A (recommended): npm install -g openclaw\n"
        "  Option B: Install Node.js from https://nodejs.org\n"
        f"  Option C: Place node.exe in {os.path.join(_EXE_DIR, 'bin')}\\"
    )


# ─── OpenClaw home dir ────────────────────────────────────────────────────────
def _get_openclaw_home() -> str:
    system_home = os.path.join(os.path.expanduser("~"), ".openclaw")
    env_home    = os.environ.get("OPENCLAW_HOME", "")
    if env_home:
        if os.path.isfile(os.path.join(env_home, "openclaw.json")):
            return env_home
        candidate = os.path.join(env_home, ".openclaw")
        if os.path.isfile(os.path.join(candidate, "openclaw.json")):
            return candidate
    exe_home = os.path.join(_EXE_DIR, ".openclaw")
    if os.path.exists(exe_home):
        return exe_home
    return system_home


# ─── State ────────────────────────────────────────────────────────────────────
_process:      subprocess.Popen | None = None
_gateway_port: int                     = 18789
_gateway_log:  list[str]               = []
_qr_data:      str | None              = None
_status:       str                     = "stopped"

MAX_LOG_LINES = 200


def _get_config() -> dict:
    config_path = os.path.join(_get_openclaw_home(), "openclaw.json")
    try:
        if not os.path.isfile(config_path):
            return {}
        with open(config_path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _is_gateway_alive(port: int | None = None) -> bool:
    import socket
    p = port or _gateway_port
    try:
        with socket.create_connection(("127.0.0.1", p), timeout=1):
            return True
    except Exception:
        return False


def _reader_thread(pipe, label: str):
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
            low = line.lower()
            if "gateway" in low and any(w in low for w in ("ready", "listening", "started")):
                _status = "running"
            if "error" in low:
                logger.warning(f"[OpenClaw] {line}")
    except Exception as e:
        logger.error(f"[OpenClaw reader] {e}")


# ─── Public API ───────────────────────────────────────────────────────────────

def start_gateway(port: int | None = None) -> dict:
    """Start the OpenClaw gateway process, auto-installing openclaw if needed."""
    global _process, _gateway_port, _status, _gateway_log, _qr_data

    config        = _get_config()
    _gateway_port = port or config.get("gateway", {}).get("port", 18789)

    if _is_gateway_alive(_gateway_port):
        _status = "running"
        return {"success": True, "message": f"Gateway already running on port {_gateway_port}",
                "status": "running", "port": _gateway_port}

    if _process and _process.poll() is None:
        return {"success": True, "message": "Gateway process already starting",
                "status": _status, "port": _gateway_port}

    _status = "starting"
    _gateway_log.clear()
    _qr_data = None

    # ── Ensure openclaw is installed and working ───────────────────────────────
    _gateway_log.append("[NEXUS] Checking openclaw installation…")
    if not _ensure_openclaw():
        # Still try — maybe a global binary exists
        try:
            _resolve_openclaw_command()
        except RuntimeError as e:
            _status = "error"
            _gateway_log.append(f"[NEXUS] ❌ {e}")
            return {"success": False, "message": str(e), "status": _status}

    openclaw_home = _get_openclaw_home()
    log_dir       = os.path.join(openclaw_home, "logs")
    os.makedirs(log_dir, exist_ok=True)
    stdout_path = os.path.join(log_dir, "gateway-stdout.log")
    stderr_path = os.path.join(log_dir, "gateway-stderr.log")

    try:
        argv = _resolve_openclaw_command()
    except RuntimeError as e:
        _status = "error"
        return {"success": False, "message": str(e), "status": _status}

    cmd = argv + ["gateway", "run", "--port", str(_gateway_port), "--allow-unconfigured"]

    logger.info(f"[OpenClaw] Command : {' '.join(cmd)}")
    logger.info(f"[OpenClaw] Home    : {openclaw_home}")
    _gateway_log.append(f"[NEXUS] Starting: {' '.join(cmd)}")

    env = os.environ.copy()
    openclaw_parent = (
        openclaw_home
        if not openclaw_home.rstrip("/\\").endswith(".openclaw")
        else os.path.dirname(openclaw_home)
    )
    env["OPENCLAW_HOME"] = openclaw_parent
    env["HOME"]          = openclaw_parent
    env["USERPROFILE"]   = openclaw_parent

    CREATE_NO_WINDOW   = 0x08000000 if os.name == "nt" else 0
    creation_flags     = CREATE_NO_WINDOW | (subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)

    stdout_log = open(stdout_path, "a", encoding="utf-8")
    stderr_log = open(stderr_path, "a", encoding="utf-8")

    try:
        _process = subprocess.Popen(
            cmd,
            shell=False,
            stdout=stdout_log,
            stderr=stderr_log,
            creationflags=creation_flags,
            text=True,
            env=env,
        )
    except FileNotFoundError:
        _status = "error"
        stdout_log.close(); stderr_log.close()
        return {"success": False,
                "message": f"'{cmd[0]}' not found. Install openclaw: npm install -g openclaw",
                "status": _status}
    except Exception as e:
        _status = "error"
        try: stdout_log.close()
        except: pass
        try: stderr_log.close()
        except: pass
        return {"success": False, "message": str(e), "status": _status}

    # Poll up to 60 s for gateway to be live
    try:
        for _ in range(60):
            time.sleep(1)
            if _is_gateway_alive(_gateway_port):
                _status = "running"
                _gateway_log.append(f"[NEXUS] ✅ Gateway live on port {_gateway_port}")
                logger.info(f"[OpenClaw] Gateway live on port {_gateway_port}")
                return {"success": True, "message": f"Gateway started on port {_gateway_port}",
                        "status": "running", "port": _gateway_port}
            if _process.poll() is not None:
                stdout_log.flush(); stderr_log.flush()
                try:
                    with open(stderr_path, "r", encoding="utf-8") as f:
                        err = f.read().strip()[-2000:]
                except Exception:
                    err = "unknown error"

                # ── Detect native module crash → trigger fresh npm install ─────
                if "ERR_MODULE_NOT_FOUND" in err or "Cannot find" in err:
                    _gateway_log.append("[NEXUS] ⚠ Native module error detected — reinstalling openclaw…")
                    logger.warning("[OpenClaw] ERR_MODULE_NOT_FOUND detected, forcing fresh npm install")
                    global _install_done, _install_failed, _validated_script
                    _install_done    = False
                    _install_failed  = False
                    _validated_script = None

                    if _ensure_openclaw():
                        # Retry gateway start with fresh install
                        _gateway_log.append("[NEXUS] Retrying gateway with freshly installed openclaw…")
                        return start_gateway(port)

                _status = "error"
                _gateway_log.append(f"[NEXUS] ❌ Gateway exited: {err}")
                return {"success": False, "message": f"Gateway exited early:\n{err}", "status": _status}

        _status = "starting"
        _gateway_log.append("⚠ Gateway process running, port not ready yet")
        return {"success": True,
                "message": f"Gateway process started (PID {_process.pid}), waiting for port...",
                "status": "starting", "port": _gateway_port}
    finally:
        try: stdout_log.close()
        except: pass
        try: stderr_log.close()
        except: pass


def stop_gateway() -> dict:
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
    global _status
    if _is_gateway_alive():
        _status = "running"
    elif _process and _process.poll() is None:
        _status = "starting"
    else:
        _status = "stopped"

    config          = _get_config()
    gateway_config  = config.get("gateway", {})
    channels_config = config.get("channels", {})

    channels_status = {}
    for name, cfg in channels_config.items():
        channels_status[name] = {**cfg, "has_token": bool(cfg.get("token"))}

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
    global _qr_data
    _qr_data = None

    openclaw_home = _get_openclaw_home()
    argv          = _resolve_openclaw_command()
    config        = _get_config()

    if channel == "whatsapp":
        cmd = argv + ["channels", "login", "--channel", channel]
    else:
        token = config.get("channels", {}).get(channel, {}).get("token")
        cmd   = argv + ["channels", "add", "--channel", channel]
        if token:
            cmd += ["--token", token]

    env                  = os.environ.copy()
    env["OPENCLAW_HOME"] = os.path.dirname(openclaw_home)
    env["HOME"]          = os.path.dirname(openclaw_home)
    env["USERPROFILE"]   = os.path.dirname(openclaw_home)

    def _pair_reader():
        global _qr_data
        try:
            CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
            proc = subprocess.Popen(
                cmd, shell=False,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, env=env,
                creationflags=CREATE_NO_WINDOW | (subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0),
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
                    if "Linked!" in line or "Ready" in line:
                        logger.info("[OpenClaw] Channel linked")
            proc.wait(timeout=60)
        except Exception as e:
            logger.error(f"[OpenClaw pairing] {e}")

    threading.Thread(target=_pair_reader, daemon=True).start()
    return {"success": True, "message": f"Pairing started for {channel}.", "qr_data": _qr_data}


def logout_channel(channel: str = "whatsapp") -> dict:
    global _qr_data
    openclaw_home = _get_openclaw_home()
    argv          = _resolve_openclaw_command()
    cmd           = argv + ["channels", "logout", "--channel", channel]

    env                  = os.environ.copy()
    env["OPENCLAW_HOME"] = os.path.dirname(openclaw_home)
    env["HOME"]          = os.path.dirname(openclaw_home)
    env["USERPROFILE"]   = os.path.dirname(openclaw_home)

    try:
        CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
        result = subprocess.run(
            cmd, shell=False, capture_output=True, text=True,
            env=env, timeout=30, creationflags=CREATE_NO_WINDOW,
        )
        output  = (result.stdout + "\n" + result.stderr).strip()
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
