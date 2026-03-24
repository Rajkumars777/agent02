"""
openclaw_client.py
==================
Forwards user messages to the local OpenClaw Gateway via WebSocket RPC.
OpenClaw uses a JSON-RPC-like protocol over WebSocket.

Protocol:
  1. Connect to ws://127.0.0.1:<port>
  2. Receive "event" type with event="connect.challenge" + nonce
  3. Send "req" type with method="connect" including device auth token
  4. Receive "event" type with event="connect.ready"  (or res ok=True)
  5. Send "req" type with method="chat.send"
  6. Receive "event" type with event="chat" (delta/final/error/aborted)

Device Auth:
  The gateway requires a registered device token from:
    ~/.openclaw/identity/device-auth.json  →  tokens.operator.token
    ~/.openclaw/identity/device.json       →  deviceId
  These are created automatically when openclaw is first run/paired.
"""

import json
import os
import logging
import uuid
import threading
import base64
import time
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

logger = logging.getLogger(__name__)


# ─── Path helpers ─────────────────────────────────────────────────────────────

def _get_openclaw_home() -> str:
    """
    Return path to the .openclaw config/session directory.
    Priority:
      1. OPENCLAW_HOME environment variable
      2. .openclaw/ next to the .exe (portable frozen build)
      3. ~/.openclaw (system default fallback for persistence)
    """
    # 1. Explicit env override
    if env_home := os.environ.get("OPENCLAW_HOME"):
        return env_home

    # 2. Next to the .exe
    exe_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    project_home = os.path.join(exe_dir, ".openclaw")
    if os.path.exists(project_home):
        return project_home

    # 3. System default (preferred for persistence)
    return os.path.join(os.path.expanduser("~"), ".openclaw")


def _load_json_file(path: str) -> dict:
    """Load a JSON file, returning empty dict on any error."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


# ─── Identity helpers ─────────────────────────────────────────────────────────

def get_device_identity() -> tuple[str, str, str, str]:
    """
    Read the device identity from the openclaw identity folder.

    Returns:
        (device_id, operator_token, private_key_pem, public_key_pem)
        Strings can be empty if not found.
    """
    home = _get_openclaw_home()

    device_json      = _load_json_file(os.path.join(home, "identity", "device.json"))
    device_auth_json = _load_json_file(os.path.join(home, "identity", "device-auth.json"))

    device_id = device_json.get("deviceId", "")
    priv_pem  = device_json.get("privateKeyPem", "")
    pub_pem   = device_json.get("publicKeyPem", "")

    # Prefer the operator token (has operator.write scope)
    token = (
        device_auth_json
        .get("tokens", {})
        .get("operator", {})
        .get("token", "")
    )

    if device_id:
        logger.info(f"🦞 Device identity loaded: deviceId={device_id[:12]}...")
    else:
        logger.warning("🦞 No device identity found in ~/.openclaw/identity/device.json")

    return device_id, token, priv_pem, pub_pem


def get_gateway_config() -> tuple[int, str]:
    """Read gateway port and token from openclaw.json."""
    home = _get_openclaw_home()
    config = _load_json_file(os.path.join(home, "openclaw.json"))
    gateway = config.get("gateway", {})
    port = gateway.get("port", 18789)
    # The token can be in auth.token or remote.token
    token = gateway.get("auth", {}).get("token", "") or gateway.get("remote", {}).get("token", "")
    return port, token


# ─── Main gateway client ──────────────────────────────────────────────────────

def send_to_openclaw(user_text: str, channel: str = "nexus", sender: str = "main") -> str:
    """
    Forwards the user's UI input to the local OpenClaw Gateway via WebSocket RPC.
    Returns the agent's reply text.

    Args:
        user_text: The message to send.
        channel:   The source channel (e.g., whatsapp, telegram, nexus).
        sender:    The user identity or conversation ID from the source.
    """
    try:
        import websocket  # websocket-client library
    except ImportError:
        return "❌ websocket-client not installed. Run: pip install websocket-client"

    port, gateway_token = get_gateway_config()
    device_id, operator_token, private_key_pem, public_key_pem = get_device_identity()
    ws_url            = f"ws://127.0.0.1:{port}"

    logger.info(f"🦞 Connecting to OpenClaw: {ws_url}, device={str(device_id)[:12] if device_id else 'none'}...")

    # ── Shared state ──────────────────────────────────────────────────────────
    result_parts = []
    error_text   = ""
    connected    = False
    chat_done    = threading.Event()
    connect_done = threading.Event()

    def _gen_id() -> str:
        return str(uuid.uuid4())

    # ── Message handler ────────────────────────────────────────────────────────
    def on_message(ws, raw_msg):
        nonlocal error_text, connected

        try:
            msg = json.loads(raw_msg)
        except json.JSONDecodeError:
            logger.warning(f"🦞 Non-JSON message received: {raw_msg[:100]}")
            return

        msg_type = msg.get("type", "")

        # ── Events ──────────────────────────────────────────────────────────
        if msg_type == "event":
            event_name = msg.get("event", "")
            payload    = msg.get("payload", {}) or {}

            # Step 1: Server sends challenge → we respond with connect request
            if event_name == "connect.challenge":
                nonce = payload.get("nonce", "")
                signed_at_ms = int(time.time() * 1000)

                client_id = "cli"
                client_mode = "cli"
                role = "operator"
                scopes = ["operator.read", "operator.write", "operator.admin"]
                platform = "win32"
                device_family = "desktop"
                
                # Use gateway token if available, else fallback to operator token
                auth_token = gateway_token or operator_token

                # v3|deviceId|clientId|clientMode|role|scopes|signedAtMs|token|nonce|platform|deviceFamily
                sign_parts = [
                    "v3",
                    device_id,
                    client_id,
                    client_mode,
                    role,
                    ",".join(scopes),
                    str(signed_at_ms),
                    auth_token or "",
                    nonce,
                    platform,
                    device_family
                ]
                sign_payload = "|".join(sign_parts)

                signature = ""
                public_key_b64url = ""
                if private_key_pem and public_key_pem:
                    try:
                        # Sign
                        pk = serialization.load_pem_private_key(private_key_pem.encode('utf-8'), password=None)
                        if isinstance(pk, ed25519.Ed25519PrivateKey):
                            sig_bytes = pk.sign(sign_payload.encode('utf-8'))
                            signature = base64.urlsafe_b64encode(sig_bytes).decode('utf-8').rstrip('=')
                        
                        # Extract raw public key for handshake
                        pub = serialization.load_pem_public_key(public_key_pem.encode('utf-8'))
                        if isinstance(pub, ed25519.Ed25519PublicKey):
                            pub_bytes = pub.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
                            public_key_b64url = base64.urlsafe_b64encode(pub_bytes).decode('utf-8').rstrip('=')
                    except Exception as e:
                        logger.error(f"🦞 Failed to sign handshake: {e}")

                connect_params: dict = {
                    "minProtocol": 3,
                    "maxProtocol": 3,
                    "client": {
                        "id":         client_id,
                        "version":    "1.0.1",
                        "platform":   "win32",
                        "mode":       client_mode,
                        "deviceFamily": device_family,
                        "displayName": "OpenClaw AI Agent",
                        "instanceId": _gen_id(),
                    },
                    "role":   role,
                    "scopes": scopes,
                }

                if signature:
                    connect_params["device"] = {
                        "id": device_id,
                        "publicKey": public_key_b64url,
                        "signature": signature,
                        "signedAt": signed_at_ms,
                        "nonce": nonce
                    }
                    logger.info("🦞 Sending signed connection request")
                else:
                    logger.warning("🦞 Sending unsigned connection request (missing keys)")

                if auth_token:
                    connect_params["auth"] = {"token": auth_token}
                
                ws.send(json.dumps({
                    "type":   "req",
                    "id":     _gen_id(),
                    "method": "connect",
                    "params": connect_params,
                }))
                return

            # Step 2: Server confirms we're connected
            if event_name == "connect.ready":
                connected = True
                connect_done.set()
                logger.info("🦞 connect.ready received — authenticated successfully")
                return

            # Step 3: Chat response events
            if event_name == "chat":
                state   = payload.get("state", "")
                message = payload.get("message", {})

                if state == "delta":
                    # Streaming text fragments
                    if isinstance(message, dict):
                        content = message.get("content", [])
                        if isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    result_parts.append(block.get("text", ""))
                        elif isinstance(message.get("text"), str):
                            result_parts.append(message["text"])

                elif state == "final":
                    # Full final answer
                    if isinstance(message, dict):
                        content = message.get("content", [])
                        if isinstance(content, list):
                            texts = [
                                block.get("text", "")
                                for block in content
                                if isinstance(block, dict) and block.get("type") == "text"
                            ]
                            if texts:
                                # Replace previous fragments with the final full text
                                result_parts.clear()
                                result_parts.append("\n".join(texts))
                        elif isinstance(message.get("text"), str):
                            result_parts.clear()
                            result_parts.append(message["text"])
                        chat_done.set()

                elif state == "error":
                    error_text = payload.get("errorMessage", "Chat error")
                    chat_done.set()

                elif state == "aborted":
                    if not result_parts:
                        error_text = "Chat aborted by gateway"
                    chat_done.set()

                return

        # ── RPC Responses ──────────────────────────────────────────────────────
        if msg_type == "res":
            ok  = msg.get("ok", False)
            err = msg.get("error", {}) or {}

            if ok:
                if not connected:
                    connected = True
                    connect_done.set()
                    logger.info("🦞 Connect res ok=True — authenticated")
            else:
                err_msg    = err.get("message", "Unknown gateway error")
                err_code   = err.get("code", "")
                error_text = f"Gateway error: {err_msg}"
                logger.error(f"🦞 Gateway RPC error [{err_code}]: {err_msg}")
                connect_done.set()
                chat_done.set()

    def on_error(ws, error):
        nonlocal error_text
        error_text = f"WebSocket error: {str(error)}"
        logger.error(f"🦞 {error_text}")
        connect_done.set()
        chat_done.set()

    def on_close(ws, close_status_code, close_msg):
        logger.info(f"🦞 WebSocket closed: code={close_status_code}")
        connect_done.set()
        chat_done.set()

    def on_open(ws):
        logger.info("🦞 WebSocket opened — waiting for connect.challenge event")

    # ── Run WebSocket ──────────────────────────────────────────────────────────
    try:
        ws = websocket.WebSocketApp(
            ws_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )

        ws_thread = threading.Thread(
            target=ws.run_forever,
            kwargs={"ping_interval": 30},
            daemon=True,
        )
        ws_thread.start()

        # Wait for authentication (up to 10 s)
        if not connect_done.wait(timeout=10):
            ws.close()
            return (
                "❌ OpenClaw Gateway connection timed out.\n"
                f"Make sure the gateway is running on port {port}."
            )

        if error_text:
            ws.close()
            tip = ""
            if "device identity" in error_text.lower():
                tip = (
                    "\n💡 Tip: Ensure ~/.openclaw/identity/device-auth.json exists "
                    "and contains a valid operator token. Run `openclaw` once to create it."
                )
            elif "missing scope" in error_text.lower():
                tip = (
                    "\n💡 Tip: The device token is missing the operator.write scope. "
                    "Re-pair the device with: openclaw device pair"
                )
            return f"❌ {error_text}{tip}"

        if not connected:
            ws.close()
            return "❌ Failed to authenticate with OpenClaw Gateway."

        # ── Send chat message ──────────────────────────────────────────────────
        session_key = f"agent:{channel}:{sender}"
        chat_req    = {
            "type":   "req",
            "id":     _gen_id(),
            "method": "chat.send",
            "params": {
                "sessionKey":     session_key,
                "message":        user_text,
                "deliver":        False,
                "idempotencyKey": _gen_id(),
            },
        }
        ws.send(json.dumps(chat_req))
        logger.info(f"🦞 chat.send → session={session_key}, msg={str(user_text)[:40] if user_text else ''}...")

        # Wait for reply (up to 5 minutes for complex tasks)
        if not chat_done.wait(timeout=300):
            ws.close()
            return "❌ OpenClaw request timed out after 5 minutes."

        ws.close()

        if error_text:
            return f"❌ {error_text}"

        final_result = "".join(result_parts)
        return final_result if final_result else "✅ Task completed (no text response)."

    except ConnectionRefusedError:
        return (
            f"❌ Cannot reach OpenClaw Gateway on port {port}.\n"
            "Start it first via the control panel or run: openclaw gateway"
        )
    except Exception as e:
        logger.exception("🦞 Unexpected error in send_to_openclaw")
        return f"❌ Error communicating with OpenClaw: {str(e)}"
