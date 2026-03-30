"""
setup.py — NEXUS Agent02 Auto-Installer
========================================
Run this once to fully set up the project from scratch:
  python setup.py

What it does:
  1. Checks Python and Node.js are available
  2. Installs Python backend dependencies (pip)
  3. Installs Node.js frontend dependencies (npm)
  4. Downloads and installs OpenClaw globally (npm install -g openclaw)
  5. Runs the OpenClaw first-time onboarding wizard with your API key
  6. Writes .env and .env.local with the generated token
  7. Writes backend/config.json with your API key
"""

import sys
import os
import subprocess
import json
import shutil
import platform
import getpass

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(HERE, "backend")
OPENCLAW_DIR = os.path.join(os.path.expanduser("~"), ".openclaw")
OPENCLAW_CONFIG = os.path.join(OPENCLAW_DIR, "openclaw.json")

BANNER = r"""
  ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗
  ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝
  ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗
  ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║
  ██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║
  ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝
         Agent02 — Auto Setup Installer
"""


# ─── Helpers ──────────────────────────────────────────────────────────────────

def run(cmd, cwd=None, capture=False, check=True):
    """Run a command, print output live, and optionally capture it."""
    print(f"\n  > {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=capture,
        text=True,
        shell=(platform.system() == "Windows"),
    )
    if check and result.returncode != 0:
        err = result.stderr.strip() if capture else ""
        raise RuntimeError(f"Command failed (exit {result.returncode}): {err}")
    return result


def which(name):
    return shutil.which(name)


def print_step(n, total, msg):
    print(f"\n{'─'*60}")
    print(f"  Step {n}/{total}: {msg}")
    print(f"{'─'*60}")


def read_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_env(path, kvs: dict):
    lines = [f"{k}={v}" for k, v in kvs.items()]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ─── Steps ────────────────────────────────────────────────────────────────────

def step_check_prereqs():
    print_step(1, 7, "Checking prerequisites (Python, Node.js, npm)")
    errors = []

    py = sys.version_info
    if py < (3, 9):
        errors.append(f"Python 3.9+ required (found {py.major}.{py.minor})")
    else:
        print(f"  ✓ Python {py.major}.{py.minor}.{py.micro}")

    if which("node"):
        r = run(["node", "--version"], capture=True, check=False)
        print(f"  ✓ Node.js {r.stdout.strip()}")
    else:
        errors.append("Node.js not found. Install from https://nodejs.org/")

    if which("npm"):
        r = run(["npm", "--version"], capture=True, check=False)
        print(f"  ✓ npm {r.stdout.strip()}")
    else:
        errors.append("npm not found. Reinstall Node.js.")

    if errors:
        print("\n  ❌ Missing requirements:")
        for e in errors:
            print(f"     • {e}")
        sys.exit(1)


def step_install_python():
    print_step(2, 7, "Installing Python backend dependencies")
    venv = os.path.join(BACKEND_DIR, "venv")
    pip = os.path.join(venv, "Scripts", "pip") if platform.system() == "Windows" else os.path.join(venv, "bin", "pip")

    if not os.path.exists(venv):
        print("  Creating virtualenv...")
        run([sys.executable, "-m", "venv", venv])
    else:
        print("  Virtualenv already exists, skipping creation.")

    reqs = os.path.join(BACKEND_DIR, "requirements.txt")
    run([pip, "install", "-r", reqs, "--quiet"])
    print("  ✓ Python dependencies installed")


def step_install_node():
    print_step(3, 7, "Installing Node.js frontend dependencies")
    node_modules = os.path.join(HERE, "node_modules")
    if os.path.exists(node_modules):
        print("  node_modules already exists, running npm install to sync...")
    run(["npm", "install", "--prefer-offline"], cwd=HERE)
    print("  ✓ Node.js dependencies installed")


def step_install_openclaw():
    print_step(4, 7, "Installing OpenClaw Gateway (npm install -g openclaw)")
    if which("openclaw"):
        r = run(["openclaw", "--version"], capture=True, check=False)
        print(f"  ✓ OpenClaw already installed: {r.stdout.strip()}")
        return
    print("  Downloading and installing OpenClaw globally...")
    run(["npm", "install", "-g", "openclaw"])
    if not which("openclaw"):
        raise RuntimeError("OpenClaw installation failed. Try: npm install -g openclaw")
    print("  ✓ OpenClaw installed successfully")


def step_configure_openclaw(api_key: str, provider: str, model: str):
    print_step(5, 7, "Configuring OpenClaw with your API key")

    os.makedirs(OPENCLAW_DIR, exist_ok=True)

    cfg = read_json(OPENCLAW_CONFIG) if os.path.exists(OPENCLAW_CONFIG) else {}

    # Inject API key into auth profiles
    cfg.setdefault("auth", {}).setdefault("profiles", {})

    if provider == "openai":
        cfg["auth"]["profiles"]["openai:default"] = {
            "provider": "openai", "mode": "api_key", "apiKey": api_key
        }
        primary_model = f"openai/{model}"
    elif provider == "google":
        cfg["auth"]["profiles"]["google:default"] = {
            "provider": "google", "mode": "api_key", "apiKey": api_key
        }
        primary_model = f"google/{model}"
    elif provider == "openrouter":
        cfg["auth"]["profiles"]["openrouter:default"] = {
            "provider": "openrouter", "mode": "api_key", "apiKey": api_key
        }
        primary_model = f"openrouter/{model}"
    else:
        primary_model = model

    # Set default agent model
    cfg.setdefault("agents", {}).setdefault("defaults", {}).setdefault("model", {})
    cfg["agents"]["defaults"]["model"]["primary"] = primary_model
    cfg.setdefault("agents", {})["defaults"]["workspace"] = os.path.join(OPENCLAW_DIR, "workspace")

    # Set up gateway
    import secrets
    token = cfg.get("gateway", {}).get("auth", {}).get("token") or secrets.token_urlsafe(32)
    cfg["gateway"] = {
        "port": 18789,
        "mode": "local",
        "bind": "loopback",
        "auth": {"mode": "token", "token": token},
        "http": {"endpoints": {"chatCompletions": {"enabled": True}}},
        "nodes": {"denyCommands": []},
    }

    # Ensure workspace exists
    workspace = os.path.join(OPENCLAW_DIR, "workspace")
    os.makedirs(workspace, exist_ok=True)

    # Meta
    from datetime import datetime
    cfg.setdefault("meta", {})["lastTouchedAt"] = datetime.utcnow().isoformat() + "Z"
    cfg["meta"]["lastTouchedVersion"] = "auto-setup"

    write_json(OPENCLAW_CONFIG, cfg)
    print(f"  ✓ OpenClaw configured at {OPENCLAW_CONFIG}")
    return token


def step_write_env(api_key: str, token: str, provider: str, model: str):
    print_step(6, 7, "Writing .env and config.json files")

    # backend/.env
    write_env(os.path.join(BACKEND_DIR, ".env"), {"OPENAI_API_KEY": api_key if provider == "openai" else ""})

    # .env.local (frontend)
    write_env(os.path.join(HERE, ".env.local"), {
        "OPENCLAW_URL": "http://127.0.0.1:18789",
        "OPENCLAW_TOKEN": token,
    })

    # backend/config.json
    write_json(os.path.join(BACKEND_DIR, "config.json"), {
        "ai_provider": "openclaw",
        "api_key": api_key,
        "ai_model": model,
        "openclaw_gateway_url": "http://localhost:18789/api/v1/message",
        "openclaw_channel": "",
        "openclaw_token": token,
        "openai_api_key": api_key if provider == "openai" else "",
    })

    print("  ✓ backend/.env written")
    print("  ✓ .env.local written")
    print("  ✓ backend/config.json written")


def step_done():
    print_step(7, 7, "Setup complete!")
    print("""
  Everything is ready. To start the application run:

      start.bat       (Windows)
      bash start.sh   (Linux/Mac — if created)

  Or manually:
      Terminal 1:  openclaw gateway run
      Terminal 2:  cd backend  &&  python main.py
      Terminal 3:  npm run dev

  Then open:  http://localhost:3000
""")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(BANNER)

    # ── Collect API key and provider interactively ──
    print("═" * 60)
    print("  NEXUS requires an AI API key to function.")
    print("  Supported providers: openai, google, openrouter")
    print("═" * 60)

    provider = input("\n  Provider [openai/google/openrouter] (default: openai): ").strip().lower() or "openai"

    if provider == "openai":
        default_model = "gpt-4o-mini"
        key_hint = "sk-..."
    elif provider == "google":
        default_model = "gemini-2.0-flash"
        key_hint = "AIza..."
    else:
        provider = "openrouter"
        default_model = "google/gemini-2.0-flash-exp:free"
        key_hint = "sk-or-..."

    api_key = getpass.getpass(f"\n  Paste your {provider.capitalize()} API key ({key_hint}): ").strip()
    if not api_key:
        print("  ❌ API key cannot be empty.")
        sys.exit(1)

    model = input(f"\n  Model (default: {default_model}): ").strip() or default_model

    print(f"\n  Provider : {provider}")
    print(f"  Model    : {model}")
    confirm = input("\n  Proceed with setup? [Y/n]: ").strip().lower()
    if confirm == "n":
        print("  Setup cancelled.")
        sys.exit(0)

    try:
        step_check_prereqs()
        step_install_python()
        step_install_node()
        step_install_openclaw()
        token = step_configure_openclaw(api_key, provider, model)
        step_write_env(api_key, token, provider, model)
        step_done()
    except Exception as e:
        print(f"\n  ❌ Setup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
