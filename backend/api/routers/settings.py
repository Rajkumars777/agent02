"""
Settings API Router
===================
Endpoints for managing agent configuration:
- GET  /agent/settings  → current config (API key masked) + available models
- POST /agent/settings  → update config, reconfigure OpenClaw, reload agent
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import json
import os
import logging
import winreg
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["settings"])

# Resolve config path — honours NEXUS_CONFIG_PATH env var set by nexus_launcher
APP_DIR = os.path.join(os.path.expanduser("~"), "AppData", "Local", "NEXUS")
CONFIG_PATH = os.environ.get(
    "NEXUS_CONFIG_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config.json")
)

OPENCLAW_CONFIG = os.path.join(os.path.expanduser("~"), ".openclaw", "openclaw.json")

# ── Available model catalogue ─────────────────────────────────────────────────

MODEL_CATALOGUE = {
    "google": [
        "gemini-3.1-pro",
        "gemini-3.1-flash",
        "gemini-3.1-flash-lite-preview",
        "gemini-3.1-flash-live-preview",
        "gemini-3-pro",
        "gemini-3-flash",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemma-4-26b-it",
        "gemma-4-31b-it",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b",
        "gemini-1.0-pro",
    ],
    "openai": [
        "gpt-5.1-codex-mini",
        "codex-mini-latest",
        "gpt-4",
        "gpt-4-turbo",
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4.1-nano",
        "gpt-4o",
        "gpt-4o-2024-05-13",
        "gpt-4o-2024-08-06",
        "gpt-4o-2024-11-20",
        "gpt-4o-mini",
        "gpt-5",
        "gpt-5-chat-latest",
        "gpt-5-mini",
        "gpt-5-nano",
        "gpt-5-pro",
        "gpt-5-codex",
        "gpt-5.1",
        "gpt-5.1-chat-latest",
        "gpt-5.1-codex",
        "gpt-5.1-codex-max",
        "gpt-5.2",
        "gpt-5.2-chat-latest",
        "gpt-5.2-codex",
        "gpt-5.2-pro",
        "gpt-5.3-codex",
        "gpt-5.3-codex-spark",
        "gpt-5.4",
        "gpt-5.4-pro",
        "o1",
        "o1-pro",
        "o3",
        "o3-deep-research",
        "o3-mini",
        "o3-pro",
        "o4-mini",
        "o4-mini-deep-research",
    ],
    "anthropic": [
        "claude-opus-4.6",
        "claude-sonnet-4.6",
        "claude-haiku-4.5",
        "claude-opus-4.5",
        "claude-sonnet-4.5",
        "claude-3-7-sonnet",
        "claude-3-7-haiku",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
    ],
    "openrouter": [
        "google/gemini-3.1-pro",
        "google/gemini-3.1-flash",
        "anthropic/claude-4.6-opus",
        "anthropic/claude-4.6-sonnet",
        "openai/gpt-5.4-pro",
        "openai/gpt-5.4-mini",
        "deepseek/deepseek-r1",
        "perplexity/sonar-reasoning",
        "meta-llama/llama-4-400b",
        "meta-llama/llama-4-70b",
        "mistralai/pixtral-large",
        "qwen/qwen-2.5-72b-instruct",
        "google/gemini-pro-1.5",
        "anthropic/claude-3.5-sonnet",
        "openai/gpt-4o",
        "qwen/qwq-32b:free",
    ],
    "groq": [
        "llama-3.3-70b-versatile",
        "llama-3.1-70b-versatile",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768",
        "gemma2-9b-it",
        "qwen-2.5-72b",
        "deepseek-r1-distill-llama-70b",
        "deepseek-r1-distill-qwen-32b",
        "llama-guard-3-8b",
    ],
}

PROVIDER_DISPLAY = {
    "google":      "Google Gemini",
    "openai":      "OpenAI",
    "anthropic":   "Anthropic Claude",
    "openrouter":  "OpenRouter",
    "groq":        "Groq",
}

KEY_HINTS = {
    "google":      "AIza... key from aistudio.google.com",
    "openai":      "sk-... key from platform.openai.com",
    "anthropic":   "sk-ant-... key from console.anthropic.com",
    "openrouter":  "sk-or-... key from openrouter.ai",
    "groq":        "gsk_... key from console.groq.com",
}

def get_installed_browsers():
    """Scan Windows Registry for installed browsers."""
    browsers = []
    # Standard browser registry keys
    paths = {
        "Google Chrome": {
            "reg": r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
            "channel": "chrome"
        },
        "Microsoft Edge": {
            "reg": r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe",
            "channel": "msedge"
        },
        "Brave": {
            "reg": r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\brave.exe",
            "channel": None # Use path
        },
        "Mozilla Firefox": {
            "reg": r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\firefox.exe",
            "channel": None
        },
        "Opera": {
            "reg": r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\launcher.exe",
            "channel": None
        },
    }
    
    for name, info in paths.items():
        executable_path = None
        # Check HKLM then HKCU
        for root in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
            try:
                with winreg.OpenKey(root, info["reg"]) as key:
                    path, _ = winreg.QueryValueEx(key, "")
                    if os.path.exists(path):
                        executable_path = path
                        break
            except (FileNotFoundError, OSError):
                continue
        
        if executable_path:
            browsers.append({
                "name": name,
                "path": executable_path,
                "channel": info["channel"]
            })
            
    return browsers


def _load_config() -> dict:
    path = os.environ.get("NEXUS_CONFIG_PATH", CONFIG_PATH)
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_config(config: dict):
    path = os.environ.get("NEXUS_CONFIG_PATH", CONFIG_PATH)
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(config, f, indent=4)


def _mask_key(key: str) -> str:
    if not key or len(key) < 8:
        return "***"
    return key[:4] + "•••••••" + key[-4:]


def _reconfigure_openclaw(api_key: str, provider: str, model: str) -> str:
    """Write updated auth profile and model into ~/.openclaw/openclaw.json."""
    import secrets

    os.makedirs(os.path.dirname(OPENCLAW_CONFIG), exist_ok=True)
    openclaw_workspace = os.path.join(os.path.expanduser("~"), ".openclaw", "workspace")
    os.makedirs(openclaw_workspace, exist_ok=True)

    existing = {}
    if os.path.exists(OPENCLAW_CONFIG):
        try:
            with open(OPENCLAW_CONFIG, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            pass

    # Reuse existing gateway token
    token = (
        existing.get("gateway", {}).get("auth", {}).get("token") or
        existing.get("gateway", {}).get("remote", {}).get("token") or
        secrets.token_urlsafe(32)
    )

    if provider == "openai":
        primary_model = f"openai/{model}"
    elif provider in ("google", "gemini"):
        primary_model = f"google/{model}"
    elif provider == "anthropic":
        primary_model = f"anthropic/{model}"
    elif provider == "groq":
        primary_model = f"groq/{model}"
    else:
        primary_model = model if "/" in model else f"openrouter/{model}"

    # Update auth-profiles.json (The correct location for credentials in v2026.3.7)
    AUTH_PROFILES_PATH = os.path.join(os.path.expanduser("~"), ".openclaw", "agents", "main", "agent", "auth-profiles.json")
    os.makedirs(os.path.dirname(AUTH_PROFILES_PATH), exist_ok=True)
    
    auth_data = {"version": 1, "profiles": {}, "lastGood": {}, "usageStats": {}}
    if os.path.exists(AUTH_PROFILES_PATH):
        try:
            with open(AUTH_PROFILES_PATH, "r", encoding="utf-8") as f:
                auth_data = json.load(f)
        except Exception:
            pass

    profile_id = f"{provider}:default"
    auth_data.setdefault("profiles", {})[profile_id] = {
        "provider": provider,
        "mode": "api_key",
        "type": "api_key",
        "key": api_key
    }
    
    # Write updated auth-profiles.json
    with open(AUTH_PROFILES_PATH, "w", encoding="utf-8") as f:
        json.dump(auth_data, f, indent=2, ensure_ascii=False)

    # ── Update openclaw.json (Main config) ───────────────────────────────────
    cfg = existing
    # Remove 'auth' section from openclaw.json to prevent "Unrecognized key" errors
    if "auth" in cfg:
        del cfg["auth"]

    cfg["agents"] = {
        "defaults": {
            "model": {"primary": primary_model},
            "workspace": openclaw_workspace,
        }
    }
    gw = cfg.setdefault("gateway", {})
    gw["port"] = 18789
    gw["mode"] = "local"
    gw["bind"] = "loopback"
    gw.setdefault("auth", {})["mode"] = "token"
    gw["auth"]["token"] = token
    gw.setdefault("remote", {})["token"] = token
    gw.setdefault("http", {}).setdefault("endpoints", {}).setdefault("chatCompletions", {})["enabled"] = True
    gw.setdefault("nodes", {})["denyCommands"] = []

    with open(OPENCLAW_CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

    logger.info(f"OpenClaw reconfigured: provider={provider}, model={model}")
    return token


class SettingsUpdate(BaseModel):
    ai_provider: Optional[str] = None
    api_key: Optional[str] = None
    ai_model: Optional[str] = None
    openclaw_gateway_url: Optional[str] = None
    openclaw_channel: Optional[str] = None
    openclaw_token: Optional[str] = None
    browser_engine: Optional[str] = None


@router.get("/settings")
async def get_settings():
    """Return current config with the API key masked + available model catalogue."""
    config = _load_config()
    safe = dict(config)

    # Mask sensitive values
    raw_key = safe.pop("api_key", "")
    safe["api_key_masked"] = _mask_key(raw_key)
    if "openclaw_token" in safe:
        safe["openclaw_token_masked"] = _mask_key(safe.pop("openclaw_token", ""))
    if "openai_api_key" in safe:
        safe.pop("openai_api_key", "")

    # Normalise provider alias
    provider = safe.get("ai_provider", "google")
    if provider == "gemini":
        safe["ai_provider"] = "google"

    return {
        "settings": safe,
        "models": MODEL_CATALOGUE,
        "providers": PROVIDER_DISPLAY,
        "key_hints": KEY_HINTS,
        "available_browsers": get_installed_browsers(),
    }

@router.get("/browsers")
async def list_browsers():
    """Return only the list of detected browsers."""
    return {"browsers": get_installed_browsers()}


@router.post("/settings")
async def update_settings(update: SettingsUpdate):
    """Update config, reconfigure OpenClaw auth profile, and reload the agent."""
    config = _load_config()

    for field, value in update.model_dump(exclude_none=True).items():
        config[field] = value

    # Normalise provider
    if config.get("ai_provider") == "gemini":
        config["ai_provider"] = "google"

    _save_config(config)

    provider = config.get("ai_provider", "google")
    api_key  = config.get("api_key", "")
    model    = config.get("ai_model", "")

    # Always reconfigure OpenClaw so the auth profile is correct on any system
    if api_key and provider and model:
        try:
            new_token = _reconfigure_openclaw(api_key, provider, model)
            config["openclaw_token"] = new_token
            _save_config(config)
        except Exception as e:
            logger.warning(f"Could not reconfigure OpenClaw: {e}")

    # Update .env for dotenv-based code
    env_path = os.path.join(os.path.dirname(os.environ.get("NEXUS_CONFIG_PATH", CONFIG_PATH)), ".env")
    if not os.path.isabs(env_path):
        env_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            ".env"
        )

    env_lines: list[str] = []
    if api_key:
        if provider in ("google", "gemini"):
            env_lines += [f"GEMINI_API_KEY={api_key}", f"GOOGLE_API_KEY={api_key}"]
        elif provider == "openai":
            env_lines.append(f"OPENAI_API_KEY={api_key}")
        elif provider == "anthropic":
            env_lines.append(f"ANTHROPIC_API_KEY={api_key}")
        elif provider == "groq":
            env_lines.append(f"GROQ_API_KEY={api_key}")
        elif provider == "openrouter":
            env_lines.append(f"OPENROUTER_API_KEY={api_key}")

    if env_lines:
        try:
            with open(env_path, "w") as f:
                f.write("\n".join(env_lines) + "\n")
        except Exception as e:
            logger.warning(f"Could not write .env: {e}")

    # Reload agent config
    try:
        from core.agent import reload_agent
        reload_agent()
    except Exception as e:
        logger.warning(f"Could not reload agent: {e}")

    logger.info("✅ Settings updated and OpenClaw reconfigured")
    return {
        "success": True,
        "message": "Settings saved. AI reconfigured.",
        "provider": provider,
        "model": model,
    }
