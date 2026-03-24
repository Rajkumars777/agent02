"""
Settings API Router
===================
Endpoints for managing agent configuration:
- GET  /agent/settings  → current config (API key masked)
- POST /agent/settings  → update config and reload agent
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import json
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["settings"])

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config.json")


def _load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_config(config: dict):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=4)


def _mask_key(key: str) -> str:
    if not key or len(key) < 8:
        return "***"
    return key[:4] + "..." + key[-4:]


class SettingsUpdate(BaseModel):
    ai_provider: Optional[str] = None
    api_key: Optional[str] = None
    ai_model: Optional[str] = None
    openclaw_gateway_url: Optional[str] = None
    openclaw_channel: Optional[str] = None
    openclaw_token: Optional[str] = None


@router.get("/settings")
async def get_settings():
    """Return current config with the API key masked."""
    config = _load_config()
    safe = dict(config)
    if "api_key" in safe:
        safe["api_key_masked"] = _mask_key(safe.pop("api_key", ""))
    if "openclaw_token" in safe:
        safe["openclaw_token_masked"] = _mask_key(safe.pop("openclaw_token", ""))
    return {"settings": safe}


@router.post("/settings")
async def update_settings(update: SettingsUpdate):
    """Update config and reload the agent."""
    config = _load_config()

    # Only update fields that were explicitly provided
    for field, value in update.model_dump(exclude_none=True).items():
        config[field] = value

    _save_config(config)

    # Also update .env for dotenv-based code
    env_path = os.path.join(os.path.dirname(CONFIG_PATH), ".env")
    env_lines = []
    if config.get("api_key"):
        provider = config.get("ai_provider", "gemini")
        if provider == "gemini":
            env_lines.append(f'GEMINI_API_KEY={config["api_key"]}')
            env_lines.append(f'GOOGLE_API_KEY={config["api_key"]}')
        elif provider == "openrouter":
            env_lines.append(f'OPENROUTER_API_KEY={config["api_key"]}')
        elif provider == "openai":
            env_lines.append(f'OPENAI_API_KEY={config["api_key"]}')
        elif provider == "groq":
            env_lines.append(f'GROQ_API_KEY={config["api_key"]}')

    if env_lines:
        with open(env_path, "w") as f:
            f.write("\n".join(env_lines) + "\n")

    # Reload agent config
    try:
        from core.agent import reload_agent
        reload_agent()
    except Exception as e:
        logger.warning(f"Could not reload agent: {e}")

    logger.info("✅ Settings updated successfully")
    return {"success": True, "message": "Settings saved. Agent reloaded."}
