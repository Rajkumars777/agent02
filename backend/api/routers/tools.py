from fastapi import APIRouter, Query, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import os
import json
import tempfile
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tools", tags=["tools"])


# ─── File Browser ─────────────────────────────────────────────────────────────

@router.get("/files")
async def list_files(directory: str = Query(".", description="Directory to list")):
    """List files in the specified directory."""
    try:
        abs_path = os.path.abspath(directory)
        items = []
        if os.path.isdir(abs_path):
            for entry in os.scandir(abs_path):
                items.append({
                    "name": entry.name,
                    "isDir": entry.is_dir(),
                    "size": entry.stat().st_size if entry.is_file() else None,
                })
            return {"directory": abs_path, "items": items}
        else:
            raise HTTPException(status_code=404, detail="Directory not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Browser Automation (Kapture MCP) ─────────────────────────────────────────
#
# Requires: npx kapture-mcp server   (WebSocket at ws://localhost:61822/mcp)
# Chrome must be open with the Kapture extension installed.
# No new pip packages needed — uses aiohttp (already a dependency).

class BrowseRequest(BaseModel):
    url: str
    tab_id: Optional[str] = None

class BrowserSelectorRequest(BaseModel):
    selector: str
    tab_id: Optional[str] = None

class BrowserFillRequest(BaseModel):
    selector: str
    value: str
    tab_id: Optional[str] = None

class BrowserKeypressRequest(BaseModel):
    key: str
    tab_id: Optional[str] = None

class BrowserSelectRequest(BaseModel):
    selector: str
    value: str
    tab_id: Optional[str] = None

class BrowserPointRequest(BaseModel):
    x: int
    y: int
    tab_id: Optional[str] = None

class BrowserNewTabRequest(BaseModel):
    url: str = ""

class BrowserCloseTabRequest(BaseModel):
    tab_id: str

class BrowserAnalyzeRequest(BaseModel):
    question: str
    tab_id: Optional[str] = None

class BrowserTabRequest(BaseModel):
    tab_id: Optional[str] = None

class BrowserAgentTaskRequest(BaseModel):
    instruction: str
    use_vision: bool = False   # opt-in Vision mode (more expensive)


# ── Status & Discovery ────────────────────────────────────────────────────────

@router.get("/browser/status")
async def browser_status():
    """Check if Kapture MCP server is running and return open tabs."""
    from capabilities.kapture_client import is_available, list_tabs
    running = await is_available()
    result = {"running": running, "server": "ws://localhost:61822/mcp", "tabs": []}
    if running:
        tabs = await list_tabs()
        result["tabs"] = tabs.get("result", "")
    return result

@router.get("/browser/tools")
async def browser_tools_list():
    """List all Kapture MCP tools available for browser automation."""
    from capabilities.kapture_client import list_tools
    return await list_tools()


# ── Tab Management ────────────────────────────────────────────────────────────

@router.get("/browser/tabs")
async def browser_list_tabs():
    """List all open Chrome tabs with IDs, URLs, and titles."""
    from capabilities.kapture_client import list_tabs
    return await list_tabs()

@router.post("/browser/new-tab")
async def browser_new_tab(req: BrowserNewTabRequest):
    """Open a new Chrome tab, optionally navigating to a URL."""
    from capabilities.kapture_client import new_tab
    return await new_tab(req.url)

@router.post("/browser/close-tab")
async def browser_close_tab(req: BrowserCloseTabRequest):
    """Close a Chrome tab by its tab ID."""
    from capabilities.kapture_client import close_tab
    return await close_tab(req.tab_id)

@router.post("/browser/show-tab")
async def browser_show_tab(req: BrowserTabRequest):
    """Bring a tab to the foreground."""
    from capabilities.kapture_client import show_tab
    return await show_tab(req.tab_id)


# ── Navigation ────────────────────────────────────────────────────────────────

@router.post("/browser/navigate")
async def browser_navigate(req: BrowseRequest):
    """Navigate the active Chrome tab to a URL. Waits for page load."""
    from capabilities.kapture_client import navigate
    return await navigate(req.url, req.tab_id)

@router.post("/browser/back")
async def browser_back(req: BrowserTabRequest):
    """Go back in browser history."""
    from capabilities.kapture_client import back
    return await back(req.tab_id)

@router.post("/browser/forward")
async def browser_forward(req: BrowserTabRequest):
    """Go forward in browser history."""
    from capabilities.kapture_client import forward
    return await forward(req.tab_id)

@router.post("/browser/reload")
async def browser_reload(req: BrowserTabRequest):
    """Reload the current page."""
    from capabilities.kapture_client import reload
    return await reload(req.tab_id)


# ── Page Content ──────────────────────────────────────────────────────────────

@router.get("/browser/screenshot")
async def browser_screenshot(tab_id: Optional[str] = None):
    """Capture a screenshot. Returns base64-encoded WebP image in 'result'."""
    from capabilities.kapture_client import screenshot
    return await screenshot(tab_id)

@router.get("/browser/content")
async def browser_content(tab_id: Optional[str] = None):
    """Get the full HTML DOM of the current page for reading/scraping."""
    from capabilities.kapture_client import dom
    return await dom(tab_id)

@router.get("/browser/console")
async def browser_console(tab_id: Optional[str] = None):
    """Get browser console logs from the current tab."""
    from capabilities.kapture_client import console_logs
    return await console_logs(tab_id)

@router.post("/browser/elements")
async def browser_elements(req: BrowserSelectorRequest):
    """Query DOM elements matching a CSS selector. Returns element metadata."""
    from capabilities.kapture_client import elements
    return await elements(req.selector, req.tab_id)

@router.post("/browser/elements-from-point")
async def browser_elements_from_point(req: BrowserPointRequest):
    """Get elements at a specific screen coordinate (x, y)."""
    from capabilities.kapture_client import elements_from_point
    return await elements_from_point(req.x, req.y, req.tab_id)


# ── Interactions ──────────────────────────────────────────────────────────────

@router.post("/browser/click")
async def browser_click(req: BrowserSelectorRequest):
    """Click a DOM element by CSS selector."""
    from capabilities.kapture_client import click
    return await click(req.selector, req.tab_id)

@router.post("/browser/fill")
async def browser_fill(req: BrowserFillRequest):
    """Fill an input field with a value. Clears existing content first."""
    from capabilities.kapture_client import fill
    return await fill(req.selector, req.value, req.tab_id)

@router.post("/browser/hover")
async def browser_hover(req: BrowserSelectorRequest):
    """Hover the mouse over an element (useful for dropdowns/tooltips)."""
    from capabilities.kapture_client import hover
    return await hover(req.selector, req.tab_id)

@router.post("/browser/focus")
async def browser_focus(req: BrowserSelectorRequest):
    """Focus an element (move cursor to an input field)."""
    from capabilities.kapture_client import focus
    return await focus(req.selector, req.tab_id)

@router.post("/browser/keypress")
async def browser_keypress(req: BrowserKeypressRequest):
    """Press a keyboard key. Examples: 'Enter', 'Tab', 'Escape', 'ArrowDown'"""
    from capabilities.kapture_client import keypress
    return await keypress(req.key, req.tab_id)

@router.post("/browser/select")
async def browser_select(req: BrowserSelectRequest):
    """Select an option from a <select> dropdown by value."""
    from capabilities.kapture_client import select
    return await select(req.selector, req.value, req.tab_id)


# ── Vision Analysis (Screenshot + AI Vision) ─────────────────────────────

@router.post("/browser/analyze")
async def browser_analyze(req: BrowserAnalyzeRequest):
    """
    Screenshot the current page and analyze it with AI Vision (Gemini / OpenAI).
    Ask any question about what is visible on screen:
      - 'What is the CSS selector for the search input?'
      - 'Is there a CAPTCHA or login wall blocking the page?'
      - 'List all form fields and their selectors'
      - 'What is the main headline on this page?'
    Returns AI analysis with selectors, page state, and actions needed.
    """
    from capabilities.vision_browser import analyze_page
    return await analyze_page(req.question, req.tab_id)

@router.get("/browser/ensure-tab")
async def browser_ensure_tab():
    """
    Ensure at least one Chrome tab is connected to Kapture.
    If no tabs exist, automatically opens a new one.
    Returns the active tab_id.
    """
    from capabilities.kapture_client import _session
    tid = await _session.get_active_tab_id(auto_create=True)
    if tid:
        return {"success": True, "tab_id": tid}
    return {
        "success": False,
        "error": "No Chrome tab available. Make sure Chrome is open with the Kapture extension enabled."
    }

@router.get("/browser/check-disruption")
async def browser_check_disruption(tab_id: Optional[str] = None):
    """
    Detect if the page has a disruption requiring user input:
    login walls, CAPTCHAs, password prompts, 2FA, cookie banners.
    Returns disruption type and the message to show the user.
    """
    from capabilities.vision_browser import detect_disruption
    return await detect_disruption(tab_id)


# ── Autonomous Agent Task (browser-use + Playwright) ──────────────────────────
#
# Executes a natural-language instruction autonomously in a persistent
# Playwright browser. Progress is streamed back to the client via SSE
# (Server-Sent Events) so the frontend can render step-by-step updates.
#
# Requires: pip install browser-use playwright langchain-openai langchain-google-genai
#           playwright install chromium --with-deps

@router.post("/browser/agent-task")
async def browser_agent_task(req: BrowserAgentTaskRequest):
    """
    Run a high-level, natural-language web automation task autonomously.

    The agent plans and executes multi-step browser interactions without
    requiring explicit selectors or page scripts.

    Examples:
      - "Search for the latest AI news and summarize the top 3 articles"
      - "Go to github.com/trending and list the top 5 Python repos today"
      - "Find the current price of NVIDIA stock on Google Finance"

    Returns a Server-Sent Events (text/event-stream) stream. Each event is:
      data: {"status": "running", "thought": "...", "action": "..."}
      data: {"status": "done",    "result": "..."}
      data: {"status": "error",   "message": "..."}
    """
    from capabilities.browser_use_client import browser_client

    use_vision = req.use_vision

    async def event_stream():
        try:
            # Route to vision-aware agent if explicitly requested
            task_gen = (
                browser_client.run_task_with_vision(req.instruction)
                if use_vision
                else browser_client.run_task(req.instruction)
            )
            async for update in task_gen:
                # SSE format: each event must be `data: <json>\n\n`
                yield f"data: {json.dumps(update)}\n\n"

        except RuntimeError as e:
            # Browser couldn't start (e.g., Playwright not installed yet)
            err = {"status": "error", "message": str(e)}
            yield f"data: {json.dumps(err)}\n\n"
        except Exception as e:
            logger.error(f"[AgentTask] Unhandled error: {e}")
            err = {"status": "error", "message": str(e)}
            yield f"data: {json.dumps(err)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # Prevent nginx from buffering SSE
        },
    )


# ─── Desktop Management ───────────────────────────────────────────────────────

class DesktopAppRequest(BaseModel):
    app_name: str

@router.get("/desktop/processes")
async def list_processes():
    from capabilities.desktop import list_processes as lp
    return {"processes": lp()}

@router.post("/desktop/open")
async def open_desktop_app(req: DesktopAppRequest):
    from capabilities.desktop import open_app
    return open_app(req.app_name)

@router.post("/desktop/close")
async def close_desktop_app(req: DesktopAppRequest):
    from capabilities.desktop import close_app
    return close_app(req.app_name)

class DesktopTypeRequest(BaseModel):
    text: str

@router.post("/desktop/type")
async def desktop_type(req: DesktopTypeRequest):
    from capabilities.desktop import type_text
    return type_text(req.text)

class DesktopPressRequest(BaseModel):
    key: str

@router.post("/desktop/press")
async def desktop_press(req: DesktopPressRequest):
    from capabilities.desktop import press_key
    return press_key(req.key)

class DesktopClickRequest(BaseModel):
    x: int
    y: int

@router.post("/desktop/click")
async def desktop_click(req: DesktopClickRequest):
    from capabilities.desktop import click_at
    return click_at(req.x, req.y)

@router.get("/desktop/screen-size")
async def desktop_screen_size():
    from capabilities.desktop import get_screen_size
    return get_screen_size()

class OpenPathRequest(BaseModel):
    path: str

@router.post("/desktop/open-path")
async def open_system_path(req: OpenPathRequest):
    from capabilities.desktop import open_path
    return open_path(req.path)

class DeletePathRequest(BaseModel):
    path: str

@router.post("/desktop/delete")
async def delete_system_path(req: DeletePathRequest):
    from capabilities.desktop import delete_path
    return delete_path(req.path)


# ─── Voice Transcription (Offline Whisper) ────────────────────────────────────

_whisper_model = None
_whisper_lock = None

def _get_whisper_model():
    """Lazy-load and cache the Whisper model (thread-safe)."""
    global _whisper_model, _whisper_lock
    import threading
    if _whisper_lock is None:
        _whisper_lock = threading.Lock()
    with _whisper_lock:
        if _whisper_model is None:
            try:
                from faster_whisper import WhisperModel
                logger.info("[Whisper] Loading base model (first time — ~140 MB download)...")
                _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
                logger.info("[Whisper] Model (tiny/int8) loaded and cached.")
            except ImportError:
                return None
    return _whisper_model


@router.get("/voice/status")
async def whisper_status():
    """Check if faster-whisper is installed and the model is ready."""
    try:
        import faster_whisper  # noqa: F401
        model_ready = _whisper_model is not None
        return {
            "installed": True,
            "model_ready": model_ready,
            "model_name": "tiny",
        }
    except ImportError:
        return {"installed": False, "model_ready": False, "model_name": None}


@router.post("/voice/transcribe")
async def transcribe_voice(file: UploadFile = File(...)):
    """
    Transcribe an audio file using locally-running faster-whisper (fully offline).
    Accepts: webm, wav, mp4, ogg, flac, m4a
    Returns: { text, language, duration_s, segments }
    """
    model = _get_whisper_model()
    if model is None:
        raise HTTPException(
            status_code=501,
            detail=(
                "faster-whisper is not installed. "
                "Run: pip install faster-whisper  (then restart the backend)"
            ),
        )

    filename = file.filename or "audio.webm"
    suffix = os.path.splitext(filename)[1]
    if not suffix:
        content_type = file.content_type or ""
        ext_map = {
            "audio/webm": ".webm", "audio/wav": ".wav",
            "audio/ogg": ".ogg",  "audio/mp4": ".mp4",
            "audio/mpeg": ".mp3", "audio/flac": ".flac",
        }
        suffix = ext_map.get(content_type, ".webm")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        logger.info(f"[Whisper] Transcribing: {tmp_path} ({suffix})")
        import asyncio
        segments_iter, info = await asyncio.to_thread(
            model.transcribe,
            tmp_path,
            beam_size=1,
            best_of=1,
            language="en",
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=200),
            temperature=0,
        )
        segments = list(segments_iter)
        text = " ".join(s.text.strip() for s in segments).strip()
        logger.info(f"[Whisper] Result ({info.language}): {text[:80]}")
        return {
            "text": text,
            "language": info.language,
            "language_probability": round(info.language_probability, 3),
            "duration_s": round(info.duration, 2),
            "segments": len(segments),
        }
    except Exception as e:
        logger.error(f"[Whisper] Transcription error: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
