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
from typing import Optional, Callable
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

logger = logging.getLogger(__name__)


# ─── Path helpers ─────────────────────────────────────────────────────────────

def _get_openclaw_home() -> str:
    """
    Return the path to the .openclaw config/session directory.

    Handles two OPENCLAW_HOME conventions:
      - Node.js style: OPENCLAW_HOME = parent of .openclaw  (e.g. C:\\Users\\rajak)
      - Direct style:  OPENCLAW_HOME = the .openclaw dir itself

    Priority:
      1. OPENCLAW_HOME env var (auto-detects which convention)
      2. .openclaw/ next to the .exe (portable frozen build)
      3. ~/.openclaw (system default)
    """
    system_default = os.path.join(os.path.expanduser("~"), ".openclaw")

    env_home = os.environ.get("OPENCLAW_HOME", "")
    if env_home:
        # Direct: OPENCLAW_HOME points straight to .openclaw dir
        if os.path.exists(os.path.join(env_home, "openclaw.json")):
            return env_home
        # Node.js style: OPENCLAW_HOME is the parent — look for .openclaw subdir
        candidate = os.path.join(env_home, ".openclaw")
        if os.path.exists(os.path.join(candidate, "openclaw.json")):
            return candidate
        # env var set but config not found there; fall through to system default

    # Next to the .exe (portable build)
    exe_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    project_home = os.path.join(exe_dir, ".openclaw")
    if os.path.exists(project_home):
        return project_home

    return system_default


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
        logger.info(f"[OpenClaw] Device identity loaded: deviceId={device_id[:12]}...")
    else:
        logger.warning("[OpenClaw] No device identity found in ~/.openclaw/identity/device.json")

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


def _get_dynamic_system_context() -> str:
    import platform
    import getpass
    import time
    
    home_dir = os.path.expanduser("~")
    user_name = getpass.getuser()
    os_name = platform.system()
    os_release = platform.release()
    current_time = time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime())
    
    # Check if a custom USER.md profile exists
    openclaw_home = _get_openclaw_home()
    user_md_path = os.path.join(openclaw_home, "workspace", "USER.md")
    custom_profile = ""
    if os.path.exists(user_md_path):
        try:
            with open(user_md_path, "r", encoding="utf-8") as f:
                custom_profile = f"\n--- USER PROFILE OVERRIDES (from USER.md) ---\n{f.read()}\n---------------------------------------------\n"
        except Exception:
            pass

    return (
        f"--- DYNAMIC SYSTEM CONTEXT ---\n"
        f"Operating System: {os_name} {os_release}\n"
        f"Current User: {user_name}\n"
        f"Home Directory: {home_dir}\n"
        f"Desktop folder: {os.path.join(home_dir, 'Desktop')}\n"
        f"Documents folder: {os.path.join(home_dir, 'Documents')}\n"
        f"Downloads folder: {os.path.join(home_dir, 'Downloads')}\n"
        f"Current Time: {current_time}\n"
        f"{custom_profile}\n"
    )

# ─── Main gateway client ──────────────────────────────────────────────────────

def send_to_openclaw(user_text: str, channel: str = "nexus", sender: str = "main", files: list[dict] = None, on_delta: Optional[Callable[[str], None]] = None) -> str:
    """
    Forwards the user's UI input to the local OpenClaw Gateway via WebSocket RPC.
    Returns the agent's reply text.

    Args:
        user_text: The message to send.
        channel:   The source channel (e.g., whatsapp, telegram, nexus).
        sender:    The user identity or conversation ID from the source.
        files:     List of files with { name, type, data } (base64).
    """
    try:
        import websocket  # websocket-client library
    except ImportError:
        return "❌ websocket-client not installed. Run: pip install websocket-client"

    port, gateway_token = get_gateway_config()
    device_id, operator_token, private_key_pem, public_key_pem = get_device_identity()
    ws_url            = f"ws://127.0.0.1:{port}"

    logger.info(f"[OpenClaw] Connecting to OpenClaw: {ws_url}, device={str(device_id)[:12] if device_id else 'none'}...")

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
            logger.warning(f"[OpenClaw] Non-JSON message received: {raw_msg[:100]}")
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
                        logger.error(f"[OpenClaw] Failed to sign handshake: {e}")

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
                    logger.info("[OpenClaw] Sending signed connection request")
                else:
                    logger.warning("[OpenClaw] Sending unsigned connection request (missing keys)")

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
                logger.info("[OpenClaw] connect.ready received — authenticated successfully")
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
                                    txt = block.get("text", "")
                                    result_parts.append(txt)
                                    if on_delta: on_delta(txt)
                        elif isinstance(message.get("text"), str):
                            txt = message["text"]
                            result_parts.append(txt)
                            if on_delta: on_delta(txt)

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
                    logger.info("[OpenClaw] Connect res ok=True — authenticated")
            else:
                err_msg    = err.get("message", "Unknown gateway error")
                err_code   = err.get("code", "")
                error_text = f"Gateway error: {err_msg}"
                logger.error(f"[OpenClaw] Gateway RPC error [{err_code}]: {err_msg}")
                connect_done.set()
                chat_done.set()

    def on_error(ws, error):
        nonlocal error_text
        error_text = f"WebSocket error: {str(error)}"
        logger.error(f"[OpenClaw] {error_text}")
        connect_done.set()
        chat_done.set()

    def on_close(ws, close_status_code, close_msg):
        logger.info(f"[OpenClaw] WebSocket closed: code={close_status_code}")
        connect_done.set()
        chat_done.set()

    def on_open(ws):
        logger.info("[OpenClaw] WebSocket opened — waiting for connect.challenge event")

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

        # Inject aggressive automation directives and UI policies
        system_prefix = (
            "SYSTEM DIRECTIVE: You are an autonomous desktop agent with full terminal, file, and OS access.\n"
            "1. You MUST perform tasks autonomously by writing and executing code.\n"
            "2. NEVER ask for permission. NEVER give tutorials. Just DO IT dynamically.\n"
            "3. DO NOT output your internal 'Steps:', plans, or thought processes in the chat reply. Just do the task and provide a concise, polished final response.\n"
            "4. CRITICAL: For informational queries (e.g. 'list files', 'read file', 'check processes'), YOU MUST PRINT THE ABSOLUTE ENTIRE LIST directly in the chat. DO NOT summarize. DO NOT truncate. DO NOT say 'it is too long'. DO NOT save it to a file unless explicitly asked! Just print EVERY SINGLE ITEM no matter how many there are.\n"
            "5. When listing files or directories, you MUST always output the FULL, ABSOLUTE Windows path (e.g., `C:\\Users\\...`) for EVERY single item. The UI automatically makes absolute paths clickable.\n"
            "6. ONLY when the user explicitly asks you to generate, download, or create a specific file/report, store it in the user's `Downloads` directory by default.\n"
            "7. If a task is unfinished, undone, or encounters an error, you MUST format that specific text using HTML for bold red (e.g., `<span style=\"color:#ef4444; font-weight:bold\">ERROR: your message</span>`).\n"
            "8. Make your final response beautiful and premium using elegant markdown formatting and tables when useful.\n"
            "9. If you need to manipulate Excel, Word, PPT or PDF files, first use the terminal to `pip install openpyxl python-docx python-pptx PyPDF2 pandas` before running your script.\n"
            "10. NEVER be lazy. If the user asks for all files, you give all files. No exceptions.\n"
            "11. LIVE DATA CHARTS — The NEXUS dashboard can render interactive charts directly in the chat. WHENEVER you analyze numerical data (CSV, Excel, JSON, databases, statistics, comparisons), you MUST output a chart using this EXACT format after your text summary:\n"
            "```chart\n"
            "{\n"
            "  \"type\": \"bar\",\n"
            "  \"title\": \"Chart Title\",\n"
            "  \"description\": \"What this chart shows\",\n"
            "  \"data\": [{\"label\": \"Jan\", \"value\": 120}, {\"label\": \"Feb\", \"value\": 95}],\n"
            "  \"xKey\": \"label\",\n"
            "  \"yKeys\": [\"value\"],\n"
            "  \"unit\": \"\"\n"
            "}\n"
            "```\n"
            "    CHART TYPES: use \"bar\" for comparisons, \"line\" for trends over time, \"area\" for cumulative data, \"pie\" for proportions/shares.\n"
            "    MULTIPLE SERIES: add more keys to the data objects and list them in yKeys: e.g. yKeys: [\"revenue\", \"profit\"].\n"
            "    ALWAYS include a chart when presenting: sales data, file sizes, counts, scores, time-series, survey results, financial data, or any tabular numeric data.\n"
            "    Example stacked bar: {\"type\":\"bar\", \"stacked\":true, \"xKey\":\"month\", \"yKeys\":[\"income\",\"expense\"]}\n\n"
            "12. WEB BROWSER AUTOMATION — You have a live Kapture-powered browser available via REST.\n"
            "    Chrome must be open on the user's machine with the Kapture extension active.\n"
            "    Use these endpoints (all at http://127.0.0.1:8000/tools/browser/):\n\n"
            "    NAVIGATION:\n"
            "      POST /tools/browser/navigate       {\"url\": \"https://...\"}\n"
            "      POST /tools/browser/back           {}  or {\"tab_id\": N}\n"
            "      POST /tools/browser/forward        {}\n"
            "      POST /tools/browser/reload         {}\n\n"
            "    PAGE CONTENT:\n"
            "      GET  /tools/browser/screenshot     → {result: <base64 WebP image>}\n"
            "      GET  /tools/browser/content        → {result: <full HTML DOM>}\n"
            "      GET  /tools/browser/console        → {result: <console logs>}\n"
            "      POST /tools/browser/elements       {\"selector\": \"CSS selector\"}\n\n"
            "    INTERACTIONS:\n"
            "      POST /tools/browser/click          {\"selector\": \"#btn-submit\"}\n"
            "      POST /tools/browser/fill           {\"selector\": \"#email\", \"value\": \"user@x.com\"}\n"
            "      POST /tools/browser/hover          {\"selector\": \".dropdown\"}\n"
            "      POST /tools/browser/keypress       {\"key\": \"Enter\"}  (also Tab, Escape, ArrowDown)\n"
            "      POST /tools/browser/select         {\"selector\": \"#country\", \"value\": \"IN\"}\n\n"
            "    TABS:\n"
            "      GET  /tools/browser/tabs           → list all open tabs with IDs (tab_id is a STRING like '992479167')\n"
            "      POST /tools/browser/close-tab      {\"tab_id\": \"992479167\"}\n\n"
            "    VISION (uses AI Vision to see the screen):\n"
            "      POST /tools/browser/analyze        {\"question\": \"What selectors are on this page?\"}\n"
            "      GET  /tools/browser/check-disruption  → detects login walls/CAPTCHAs\n"
            "      GET  /tools/browser/ensure-tab         → ensures a tab exists (auto-creates if needed), returns tab_id\n\n"
            "    CRITICAL RULES:\n"
            "      1. ALWAYS call GET /tools/browser/ensure-tab FIRST — it returns tab_id AND auto-opens Chrome if no tabs exist.\n"
            "      2. ALWAYS pass tab_id (a string like '992479167') in every subsequent call: {\"url\":\"...\", \"tab_id\":\"992479167\"}\n"
            "      3. tab_id is ALWAYS a string — never an integer.\n"
            "      4. After /browser/navigate, wait 1.5 seconds before calling screenshot or content.\n"
            "      5. If navigate returns a timeout error, the page still loaded. Wait 1.5s then call /browser/content.\n\n"
            "    WORKFLOW EXAMPLE (search on Amazon):\n"
            "      Step 1: GET /tools/browser/ensure-tab → get tab_id (e.g. '992479167')\n"
            "      Step 2: POST /tools/browser/navigate {\"url\":\"https://amazon.com\", \"tab_id\":\"992479167\"}\n"
            "      Step 3: Wait 1.5 seconds\n"
            "      Step 4: POST /tools/browser/fill {\"selector\":\"#twotabsearchtextbox\", \"value\":\"iphone\", \"tab_id\":\"992479167\"}\n"
            "      Step 5: POST /tools/browser/keypress {\"key\":\"Enter\", \"tab_id\":\"992479167\"}\n\n"
            "13. DISRUPTION HANDLING — If automation hits a login wall, CAPTCHA, password prompt, or 2FA:\n"
            "    a. Call GET /tools/browser/check-disruption\n"
            "    b. If disruption=true: STOP automation immediately\n"
            "    c. Return the disruption.message to the user in your chat reply\n"
            "    d. Ask the user for the required value (password, OTP, etc.)\n"
            "    e. Wait for the user's next message with the value\n"
            "    f. Use POST /tools/browser/fill to enter it, then continue automation\n"
            "    EXAMPLE: 'I encountered a login wall on GitHub. Please provide your GitHub password\n"
            "    (your username github.com/yourname is already entered):'\n\n"
            f"{_get_dynamic_system_context()}"
            f"USER REQUEST: {user_text}"
        )

        # ── Multi-modal Construction ──
        if files and len(files) > 0:
            # Construct a multi-modal message object
            content_blocks = [{"type": "text", "text": system_prefix}]
            for f in files:
                mimetype = f.get("type", "application/octet-stream")
                # Strip 'data:mime/type;base64,' prefix if present
                data = f.get("data", "")
                if "," in data:
                    data = data.split(",")[1]
                
                if mimetype.startswith("image/"):
                    content_blocks.append({
                        "type": "image",
                        "image": { "data": data, "format": mimetype.split("/")[-1] }
                    })
                else:
                    # Treat as document/generic file
                    content_blocks.append({
                        "type": "file",
                        "file": { "data": data, "name": f.get("name", "file"), "mimeType": mimetype }
                    })
            
            message_payload = { "content": content_blocks }
        else:
            message_payload = system_prefix

        chat_req    = {
            "type":   "req",
            "id":     _gen_id(),
            "method": "chat.send",
            "params": {
                "sessionKey":     session_key,
                "message":        message_payload,
                "deliver":        False,
                "idempotencyKey": _gen_id(),
            },
        }
        ws.send(json.dumps(chat_req))
        logger.info(f"[OpenClaw] chat.send → session={session_key}, msg={str(user_text)[:40] if user_text else ''}...")

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
            f"❌ Gateway is still initializing or cannot be reached on port {port}.\n"
            "Please wait a few moments and try again."
        )
    except Exception as e:
        err_str = str(e)
        if "10061" in err_str or "actively refused" in err_str.lower():
            return (
                f"❌ Gateway is still initializing on port {port}.\n"
                "Please wait 10-30 seconds and try again."
            )
        logger.exception("[OpenClaw] Unexpected error in send_to_openclaw")
        return f"❌ Error communicating with OpenClaw: {err_str}"
