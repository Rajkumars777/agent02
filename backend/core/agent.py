"""
src/core/agent.py
==================
Main agent — routes execution to the OpenClaw Engine.
"""

import os
import json
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger(__name__)

# ─── Config ──────────────────────────────────────────────────────────────────

def _get_config_path():
    """Consistent configuration path lookup used by the entire backend."""
    return os.environ.get(
        "NEXUS_CONFIG_PATH",
        os.path.join(os.path.expanduser("~"), "AppData", "Local", "NEXUS", "config.json")
    )

CONFIG_PATH = _get_config_path()

def _load_config() -> dict:
    path = _get_config_path()
    try:
        with open(path, "r") as f:
            cfg = json.load(f)
            # Use environment variables as overrides for cloud keys
            if cfg.get("ai_provider") in ["google", "gemini"] and os.getenv("GEMINI_API_KEY"):
                cfg["api_key"] = os.getenv("GEMINI_API_KEY")
            elif cfg.get("ai_provider") == "openai" and os.getenv("OPENAI_API_KEY"):
                cfg["api_key"] = os.getenv("OPENAI_API_KEY")
            return cfg
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "ai_provider": "google",
            "api_key": os.getenv("GEMINI_API_KEY", ""),
            "ai_model": "gemini-1.5-flash",
        }

# Global client cache to allow hot-reloads
_cached_client = None
_cached_model = None

def reload_agent():
    """Clear the cached client state so it reloads from config.json on the next call."""
    global _cached_client
    _cached_client = None
    load_dotenv()
    logger.info("Agent reload requested: clearing LLM client cache.")

def get_client():
    global _cached_client, _cached_model
    
    if _cached_client:
        return _cached_client, _cached_model
    
    config = _load_config()
    provider = config.get("ai_provider", "google")
    api_key = config.get("api_key", os.getenv("GEMINI_API_KEY", ""))
    
    if provider in ["google", "gemini"]:
        model = config.get("ai_model", "gemini-1.5-flash").split("/")[-1]
        _cached_model = model
        _cached_client = OpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        return _cached_client, _cached_model

    if provider == "openclaw":
        model = config.get("ai_model", "gemini-1.5-flash").split("/")[-1]
        _cached_model = model
        auth_key = config.get("openclaw_token", os.getenv("GEMINI_API_KEY", ""))
        _cached_client = OpenAI(
            api_key=auth_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        return _cached_client, _cached_model

    # Default: direct OpenAI / other providers
    _cached_model = config.get("ai_model", "gpt-4o")
    _cached_client = OpenAI(api_key=api_key)
    return _cached_client, _cached_model


# ─── Main Entry Point ────────────────────────────────────────────────────────

async def run_agent(user_input: str, task_id: str = "default", channel: str = "nexus", sender: str = "main", files: list[dict] = None):
    from api.routers.events import emit_event
    from core.openclaw_client import send_to_openclaw

    await emit_event(task_id, "Thinking", {"message": "Forwarding request to OpenClaw Engine..."})

    try:
        logger.info(f"Routing execution to OpenClaw for: {user_input} (files: {len(files) if files else 0})")

        loop = asyncio.get_running_loop()

        def on_delta_callback(text: str):
            if text.strip():
                try:
                    if not loop.is_closed():
                        asyncio.run_coroutine_threadsafe(
                            emit_event(task_id, "AgentStep", {"desc": text, "tool": "OpenClaw", "success": True}),
                            loop
                        )
                except Exception:
                    pass

        result_text = await asyncio.to_thread(
            send_to_openclaw,
            user_input,
            channel=channel,
            sender=sender,
            files=files,
            on_delta=on_delta_callback
        )

        await emit_event(task_id, "AgentDone", {"result": result_text})
        return _format_response(result_text, "OpenClaw_Engine", success=True)

    except Exception as e:
        logger.error(f"Agent error connecting to OpenClaw: {e}")
        error_msg = f"Error: {str(e)}"
        await emit_event(task_id, "AgentStep", {"desc": error_msg})
        return _format_response(error_msg, "Error", success=False)


def _format_response(result_text: str, tool_name: str, success: bool = True):
    """Package the agent result into a structured step response."""
    timestamp = datetime.now().strftime("%I:%M:%S %p")
    step = {
        "type": "Action",
        "content": result_text,
        "timestamp": timestamp,
        "tool": tool_name,
        "success": success,
    }
    return {
        "success": success,
        "steps": [step],
        "intermediate_steps": [step],
    }
