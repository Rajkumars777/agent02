"""
kapture_client.py
=================
Lightweight async MCP-over-WebSocket client for Kapture browser automation.

Kapture runs as a standalone MCP server:
    npx kapture-mcp server
    → listens at ws://localhost:61822/mcp

Protocol: MCP JSON-RPC 2.0 over WebSocket.
We use aiohttp (already a dependency) for the async WebSocket transport.
No new pip packages needed.

KEY RULES (learned from Kapture internals):
  - tabId MUST be a STRING, not an integer (e.g. "992479167")
  - screenshot, dom, elements etc ALWAYS require a tabId
  - Use navigate() on an existing tab — new_tab() often can't inject content script
  - After navigate, allow 2-3s for Kapture's content script to load on the new page

PERFORMANCE:
  - A persistent WebSocket session is reused across all calls (no per-call handshake).
  - Active tab ID is cached and refreshed only when needed.
  - Session is automatically rebuilt if the connection drops.
"""

import asyncio
import json
import logging
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

KAPTURE_WS_URL = "ws://localhost:61822/mcp"
KAPTURE_HTTP_CHECK = "http://localhost:61822"

_req_id = 0


def _next_id() -> str:
    global _req_id
    _req_id += 1
    return str(_req_id)


# ─── Persistent Session Pool ──────────────────────────────────────────────────
#
# Instead of creating a new WebSocket + doing the MCP initialize handshake on
# every single call, we keep a single session alive for the process lifetime.
# If it drops, it is rebuilt transparently.

class _KaptureSession:
    """A long-lived, reusable MCP WebSocket session with Kapture."""

    def __init__(self):
        self._http: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._lock = asyncio.Lock()
        self._ready = False
        # Cached active tab ID — invalidated after navigate/close
        self._cached_tab_id: Optional[str] = None
        # Background keepalive task handle
        self._keepalive_task: Optional[asyncio.Task] = None

    async def _connect(self):
        """(Re)connect and perform the MCP initialize handshake."""
        # Tear down previous connection if any
        await self._close_unsafe()

        try:
            timeout = aiohttp.ClientTimeout(total=None, connect=5, sock_connect=5, sock_read=90)
            self._http = aiohttp.ClientSession(timeout=timeout)
            self._ws = await self._http.ws_connect(
                KAPTURE_WS_URL,
                heartbeat=20,          # WS-level ping every 20s
                receive_timeout=90,
            )

            # ── MCP Initialize handshake (done ONCE per session) ──────────────
            init_id = _next_id()
            await self._ws.send_json({
                "jsonrpc": "2.0",
                "id": init_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "nexus-backend",
                        "version": "1.0.0",
                    },
                },
            })

            # Wait for initialize response
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if data.get("id") == init_id:
                        break
                elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED):
                    raise ConnectionError("WebSocket closed during MCP initialize")

            # ── Initialized notification ──────────────────────────────────────
            await self._ws.send_json({
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            })

            self._ready = True
            logger.info("[Kapture] Persistent session established (WS + MCP handshake done).")

            # Start background keepalive so the server doesn't close the WS on idle
            if self._keepalive_task is None or self._keepalive_task.done():
                self._keepalive_task = asyncio.create_task(self._keepalive_loop())

        except Exception as e:
            self._ready = False
            await self._close_unsafe()
            raise ConnectionError(f"Kapture connect failed: {e}") from e

    async def _keepalive_loop(self):
        """Send a lightweight list_tabs ping every 25s to prevent idle-disconnect."""
        while True:
            await asyncio.sleep(25)
            if not self._is_alive():
                break
            try:
                # Use raw send — don't go through the lock to avoid deadlock
                ping_id = _next_id()
                await self._ws.send_json({
                    "jsonrpc": "2.0",
                    "id": ping_id,
                    "method": "tools/call",
                    "params": {"name": "list_tabs", "arguments": {}},
                })
                logger.debug("[Kapture] Keepalive ping sent.")
            except Exception:
                break  # Session will reconnect on next real call

    async def _close_unsafe(self):
        """Close WS + HTTP session ignoring errors."""
        self._ready = False
        try:
            if self._ws and not self._ws.closed:
                await self._ws.close()
        except Exception:
            pass
        try:
            if self._http and not self._http.closed:
                await self._http.close()
        except Exception:
            pass
        self._ws = None
        self._http = None

    def _is_alive(self) -> bool:
        return self._ready and self._ws is not None and not self._ws.closed

    async def call(self, tool_name: str, args: dict = None, timeout_s: int = 30) -> dict:
        """
        Call a Kapture MCP tool over the persistent session.
        Automatically reconnects if the session has dropped.
        """
        async with self._lock:
            # Reconnect if dropped
            if not self._is_alive():
                try:
                    await self._connect()
                except ConnectionError as e:
                    if "actively refused" in str(e) or "10061" in str(e) or "Cannot connect" in str(e).lower():
                        return {
                            "success": False,
                            "error": (
                                "Kapture MCP server is not running. "
                                "Start it with:  npx kapture-mcp server\n"
                                "Also make sure the Kapture Chrome extension is installed and Chrome is open."
                            ),
                        }
                    return {"success": False, "error": str(e)}

            try:
                return await asyncio.wait_for(
                    self._send_call(tool_name, args),
                    timeout=timeout_s,
                )
            except asyncio.TimeoutError:
                self._ready = False  # Force reconnect on next call
                return {"success": False, "error": f"Kapture tool '{tool_name}' timed out after {timeout_s}s"}
            except Exception as e:
                self._ready = False  # Force reconnect on next call
                logger.warning(f"[Kapture] Session error on '{tool_name}': {e}. Will reconnect next call.")
                return {"success": False, "error": str(e)}

    async def _send_call(self, tool_name: str, args: dict) -> dict:
        """Send a tools/call RPC over the existing WS and read the matching response."""
        call_id = _next_id()
        await self._ws.send_json({
            "jsonrpc": "2.0",
            "id": call_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": args or {},
            },
        })

        # Read messages until we get the response for our call_id
        async for msg in self._ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                if data.get("id") == call_id:
                    return _parse_result(data, tool_name)
                # Ignore unrelated push messages (tabs_changed, etc.)
            elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED):
                self._ready = False
                return {"success": False, "error": "WebSocket closed awaiting result"}

        self._ready = False
        return {"success": False, "error": f"No response received for tool '{tool_name}'"}

    def invalidate_tab_cache(self):
        """Call this after navigate() so that the next tab lookup is fresh."""
        self._cached_tab_id = None

    async def get_active_tab_id(self, auto_create: bool = True) -> Optional[str]:
        """
        Return the active tab ID (cached). If no tabs are connected and
        auto_create=True, opens a new Chrome tab automatically so automation
        can proceed without user intervention.
        """
        if self._cached_tab_id:
            return self._cached_tab_id
        result = await self.call("list_tabs", {})
        if not result.get("success"):
            return None
        try:
            tabs_data = json.loads(result.get("result", "{}"))
            tabs = tabs_data.get("tabs", [])
            if tabs:
                tid = str(tabs[0]["tabId"])
                self._cached_tab_id = tid
                return tid
            # No tabs connected — auto-create one if allowed
            if auto_create:
                logger.info("[Kapture] No tabs connected — opening a new Chrome tab automatically.")
                new_result = await self.call("new_tab", {}, timeout_s=20)
                if new_result.get("success"):
                    # new_tab returns the new tab details; re-query to get the ID
                    await asyncio.sleep(1.0)  # let the extension register the tab
                    tabs2 = await self.call("list_tabs", {})
                    if tabs2.get("success"):
                        tabs2_data = json.loads(tabs2.get("result", "{}"))
                        tabs2_list = tabs2_data.get("tabs", [])
                        if tabs2_list:
                            tid = str(tabs2_list[0]["tabId"])
                            self._cached_tab_id = tid
                            logger.info(f"[Kapture] Auto-created tab: {tid}")
                            return tid
                logger.warning("[Kapture] Auto-create tab failed — Chrome may not be open or extension inactive.")
        except Exception as e:
            logger.warning(f"[Kapture] Could not parse tabs: {e}")
        return None


def _parse_result(raw: dict, tool_name: str) -> dict:
    """Parse a Kapture MCP tools/call response into our standard format."""
    if "error" in raw:
        err = raw["error"]
        return {
            "success": False,
            "error": err.get("message", str(err)) if isinstance(err, dict) else str(err),
        }

    result_obj = raw.get("result", {})
    if result_obj.get("isError"):
        content = result_obj.get("content", [])
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                try:
                    err_json = json.loads(item["text"])
                    err_msg = err_json.get("error", {}).get("message", item["text"])
                except Exception:
                    err_msg = item["text"]
                return {"success": False, "error": err_msg}
        return {"success": False, "error": "Kapture returned an error"}

    content = result_obj.get("content", [])
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text":
            return {"success": True, "result": item.get("text", ""), "type": "text"}
        if item.get("type") == "image":
            return {
                "success": True,
                "result": item.get("data", ""),
                "type": "image",
                "mimeType": item.get("mimeType", "image/webp"),
            }

    return {"success": True, "result": str(result_obj), "type": "text"}


# ─── Module-level singleton session ──────────────────────────────────────────
_session = _KaptureSession()


async def _call(tool_name: str, args: dict = None, timeout_s: int = 30) -> dict:
    """Call a Kapture tool via the persistent session."""
    return await _session.call(tool_name, args, timeout_s)


async def _get_active_tab_id() -> Optional[str]:
    """Return the active tab ID (cached)."""
    return await _session.get_active_tab_id()


def _tid(tab_id) -> Optional[str]:
    """Normalize a tabId to string. Returns None if not provided."""
    if tab_id is None:
        return None
    return str(tab_id)


# ─── Status / discovery ───────────────────────────────────────────────────────

async def is_available() -> bool:
    """Quick ping — True if the Kapture MCP WebSocket server is reachable."""
    try:
        timeout = aiohttp.ClientTimeout(total=3, connect=2)
        async with aiohttp.ClientSession(timeout=timeout) as http:
            async with http.ws_connect(KAPTURE_WS_URL) as _ws:
                return True
    except Exception:
        return False


async def list_tools() -> dict:
    """Return all tools that Kapture exposes via MCP."""
    try:
        timeout = aiohttp.ClientTimeout(total=10, connect=3)
        async with aiohttp.ClientSession(timeout=timeout) as http:
            async with http.ws_connect(KAPTURE_WS_URL, heartbeat=10) as ws:
                init_id = _next_id()
                await ws.send_json({
                    "jsonrpc": "2.0",
                    "id": init_id,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "nexus-backend", "version": "1.0.0"},
                    },
                })
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        if json.loads(msg.data).get("id") == init_id:
                            break

                await ws.send_json({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

                list_id = _next_id()
                await ws.send_json({"jsonrpc": "2.0", "id": list_id, "method": "tools/list", "params": {}})

                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        raw = json.loads(msg.data)
                        if raw.get("id") == list_id:
                            tools = raw.get("result", {}).get("tools", [])
                            return {
                                "success": True,
                                "tools": [
                                    {"name": t["name"], "description": t.get("description", "")}
                                    for t in tools
                                ],
                            }

    except aiohttp.ClientConnectorError:
        return {"success": False, "error": "Kapture not running", "tools": []}
    except Exception as e:
        return {"success": False, "error": str(e), "tools": []}

    return {"success": False, "error": "No response from Kapture", "tools": []}


# ─── Tab management ───────────────────────────────────────────────────────────

async def list_tabs() -> dict:
    result = await _call("list_tabs", {})
    # Invalidate cache so get_active_tab_id re-reads on next call
    _session.invalidate_tab_cache()
    return result

async def tab_detail(tab_id) -> dict:
    return await _call("tab_detail", {"tabId": _tid(tab_id)})

async def new_tab(url: str = "") -> dict:
    """
    Open a new browser tab.
    NOTE: If the Kapture extension does not have 'Access to all sites' permission in Chrome,
    new tabs may fail to connect. Prefer using navigate() on an existing tab instead.
    """
    args = {}
    if url:
        args["url"] = url
    result = await _call("new_tab", args, timeout_s=20)
    _session.invalidate_tab_cache()
    return result

async def close_tab(tab_id) -> dict:
    result = await _call("close", {"tabId": _tid(tab_id)})
    _session.invalidate_tab_cache()
    return result

async def show_tab(tab_id=None) -> dict:
    tid = _tid(tab_id)
    if tid is None:
        tid = await _get_active_tab_id()
    args = {}
    if tid:
        args["tabId"] = tid
    return await _call("show", args)


# ─── Navigation ───────────────────────────────────────────────────────────────

async def navigate(url: str, tab_id=None) -> dict:
    """
    Navigate an existing Chrome tab to a URL.

    IMPORTANT: Prefer passing tab_id from list_tabs() rather than navigating blind.
    If no tab_id is given, auto-detects the first connected tab.
    After navigation, Kapture's content script needs 1-2s to register on the new page.
    """
    tid = _tid(tab_id)
    if tid is None:
        tid = await _get_active_tab_id()

    if tid is None:
        return {
            "success": False,
            "error": (
                "No connected Chrome tab found. "
                "Make sure Chrome is open and the Kapture extension is active. "
                "The extension must have 'Access to all sites' permission in Chrome > Extensions settings."
            ),
        }

    result = await _call("navigate", {"url": url, "tabId": tid}, timeout_s=20)
    # Invalidate tab cache after navigation so state is fresh
    _session.invalidate_tab_cache()
    return result

async def back(tab_id=None) -> dict:
    tid = _tid(tab_id) or await _get_active_tab_id()
    args = {}
    if tid:
        args["tabId"] = tid
    return await _call("back", args)

async def forward(tab_id=None) -> dict:
    tid = _tid(tab_id) or await _get_active_tab_id()
    args = {}
    if tid:
        args["tabId"] = tid
    return await _call("forward", args)

async def reload(tab_id=None) -> dict:
    tid = _tid(tab_id) or await _get_active_tab_id()
    args = {}
    if tid:
        args["tabId"] = tid
    return await _call("reload", args)


# ─── Page content ─────────────────────────────────────────────────────────────

async def dom(tab_id=None) -> dict:
    """Get the full HTML DOM of the current page. tabId is required by Kapture."""
    tid = _tid(tab_id) or await _get_active_tab_id()
    if tid is None:
        return {"success": False, "error": "No connected tab found for dom()"}
    return await _call("dom", {"tabId": tid}, timeout_s=20)

async def screenshot(tab_id=None) -> dict:
    """
    Capture a screenshot. tabId is ALWAYS required by Kapture.
    Auto-detects the active tab if not provided.
    Returns base64-encoded image in result.
    """
    tid = _tid(tab_id) or await _get_active_tab_id()
    if tid is None:
        return {"success": False, "error": "No connected tab found for screenshot()"}
    return await _call("screenshot", {"tabId": tid}, timeout_s=15)

async def console_logs(tab_id=None) -> dict:
    tid = _tid(tab_id) or await _get_active_tab_id()
    args = {}
    if tid:
        args["tabId"] = tid
    return await _call("console_logs", args)

async def elements(selector: str, tab_id=None) -> dict:
    """Query DOM elements matching a CSS selector."""
    tid = _tid(tab_id) or await _get_active_tab_id()
    if tid is None:
        return {"success": False, "error": "No connected tab found for elements()"}
    return await _call("elements", {"selector": selector, "tabId": tid})

async def elements_from_point(x: int, y: int, tab_id=None) -> dict:
    """Get elements at screen coordinates (x, y)."""
    tid = _tid(tab_id) or await _get_active_tab_id()
    args = {"x": x, "y": y}
    if tid:
        args["tabId"] = tid
    return await _call("elementsFromPoint", args)


# ─── Interactions ─────────────────────────────────────────────────────────────

async def click(selector: str, tab_id=None) -> dict:
    tid = _tid(tab_id) or await _get_active_tab_id()
    if tid is None:
        return {"success": False, "error": "No connected tab found for click()"}
    return await _call("click", {"selector": selector, "tabId": tid})

async def hover(selector: str, tab_id=None) -> dict:
    tid = _tid(tab_id) or await _get_active_tab_id()
    if tid is None:
        return {"success": False, "error": "No connected tab found for hover()"}
    return await _call("hover", {"selector": selector, "tabId": tid})

async def focus(selector: str, tab_id=None) -> dict:
    tid = _tid(tab_id) or await _get_active_tab_id()
    if tid is None:
        return {"success": False, "error": "No connected tab found for focus()"}
    return await _call("focus", {"selector": selector, "tabId": tid})

async def blur(selector: str, tab_id=None) -> dict:
    tid = _tid(tab_id) or await _get_active_tab_id()
    args = {"selector": selector}
    if tid:
        args["tabId"] = tid
    return await _call("blur", args)

async def fill(selector: str, value: str, tab_id=None) -> dict:
    """Type a value into an input field (clears existing content first)."""
    tid = _tid(tab_id) or await _get_active_tab_id()
    if tid is None:
        return {"success": False, "error": "No connected tab found for fill()"}
    return await _call("fill", {"selector": selector, "value": value, "tabId": tid})

async def select(selector: str, value: str, tab_id=None) -> dict:
    """Select a <select> dropdown option by value."""
    tid = _tid(tab_id) or await _get_active_tab_id()
    if tid is None:
        return {"success": False, "error": "No connected tab found for select()"}
    return await _call("select", {"selector": selector, "value": value, "tabId": tid})

async def keypress(key: str, tab_id=None) -> dict:
    """
    Press a keyboard key.
    Examples: 'Enter', 'Tab', 'Escape', 'ArrowDown', 'Backspace'
    """
    tid = _tid(tab_id) or await _get_active_tab_id()
    if tid is None:
        return {"success": False, "error": "No connected tab found for keypress()"}
    return await _call("keypress", {"key": key, "tabId": tid})
