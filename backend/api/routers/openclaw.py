"""
OpenClaw Management API Router
===============================
Endpoints for controlling the OpenClaw gateway process and channel pairing:
- POST /openclaw/gateway/start    → Start gateway process
- POST /openclaw/gateway/stop     → Stop gateway process
- GET  /openclaw/status            → Get gateway status, QR code, logs
- POST /openclaw/channel/pair      → Start channel pairing (produces QR)
- GET  /openclaw/config            → Get openclaw.json config
- POST /openclaw/config            → Update openclaw.json config
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import json
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/openclaw", tags=["openclaw"])

OPENCLAW_HOME = os.path.join(os.path.expanduser("~"), ".openclaw")
if not os.path.isfile(os.path.join(OPENCLAW_HOME, "openclaw.json")):
    OPENCLAW_HOME = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        ".openclaw"
    )

# ─── Gateway Control ─────────────────────────────────────────────────────────

class GatewayStartRequest(BaseModel):
    port: Optional[int] = None


@router.post("/gateway/start")
async def start_gateway(req: GatewayStartRequest = GatewayStartRequest()):
    from core.openclaw_process import start_gateway
    result = start_gateway(port=req.port)
    return result


@router.post("/gateway/stop")
async def stop_gateway():
    from core.openclaw_process import stop_gateway
    result = stop_gateway()
    return result


@router.get("/status")
async def get_status():
    from core.openclaw_process import get_status
    return get_status()


# ─── Channel Pairing ─────────────────────────────────────────────────────────

class ChannelPairRequest(BaseModel):
    channel: str = "whatsapp"


@router.post("/channel/pair")
async def pair_channel(req: ChannelPairRequest):
    from core.openclaw_process import start_channel_pairing
    import asyncio
    result = await asyncio.to_thread(start_channel_pairing, req.channel)
    return result


# ─── OpenClaw Config ──────────────────────────────────────────────────────────

@router.get("/config")
async def get_openclaw_config():
    config_path = os.path.join(OPENCLAW_HOME, "openclaw.json")
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        # Mask sensitive tokens
        if "gateway" in config and "auth" in config["gateway"]:
            token = config["gateway"]["auth"].get("token", "")
            if token:
                config["gateway"]["auth"]["token_masked"] = token[:6] + "..." + token[-4:]
                del config["gateway"]["auth"]["token"]
        return {"config": config}
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return {"error": str(e)}


class OpenClawConfigUpdate(BaseModel):
    model: Optional[str] = None
    gateway_port: Optional[int] = None
    whatsapp_enabled: Optional[bool] = None
    telegram_enabled: Optional[bool] = None
    telegram_token: Optional[str] = None
    slack_enabled: Optional[bool] = None
    slack_token: Optional[str] = None


@router.post("/config")
async def update_openclaw_config(update: OpenClawConfigUpdate):
    config_path = os.path.join(OPENCLAW_HOME, "openclaw.json")
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"error": "Could not read openclaw.json"}

    if update.model:
        config.setdefault("agents", {}).setdefault("defaults", {})["model"] = update.model

    if update.gateway_port:
        config.setdefault("gateway", {})["port"] = update.gateway_port

    if update.whatsapp_enabled is not None:
        config.setdefault("channels", {}).setdefault("whatsapp", {})["enabled"] = update.whatsapp_enabled
        config.setdefault("plugins", {}).setdefault("entries", {}).setdefault("whatsapp", {})["enabled"] = update.whatsapp_enabled

    if update.telegram_enabled is not None:
        config.setdefault("channels", {}).setdefault("telegram", {})["enabled"] = update.telegram_enabled
        config.setdefault("plugins", {}).setdefault("entries", {}).setdefault("telegram", {})["enabled"] = update.telegram_enabled

    if update.telegram_token:
        config.setdefault("channels", {}).setdefault("telegram", {})["token"] = update.telegram_token

    if update.slack_enabled is not None:
        config.setdefault("channels", {}).setdefault("slack", {})["enabled"] = update.slack_enabled
        config.setdefault("plugins", {}).setdefault("entries", {}).setdefault("slack", {})["enabled"] = update.slack_enabled

    if update.slack_token:
        config.setdefault("channels", {}).setdefault("slack", {})["token"] = update.slack_token

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    return {"success": True, "message": "OpenClaw config updated"}


@router.post("/channel/logout")
async def logout_openclaw_channel(request: ChannelPairRequest):
    """Log out of a channel account."""
    from core.openclaw_process import logout_channel
    result = logout_channel(request.channel)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message"))
    return result
