from fastapi import APIRouter, Query, HTTPException, UploadFile, File
from pydantic import BaseModel
import os
import tempfile
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tools", tags=["tools"])

class BrowseRequest(BaseModel):
    url: str

@router.get("/files")
async def list_files(directory: str = Query(".", description="Directory to list")):
    """List files in the specified directory."""
    try:
        # Resolve path relative to project root or absolute
        abs_path = os.path.abspath(directory)
        
        # Security check: Limit to current drive/user home for sanity (basic)
        # In a real app, this should be more restricted
        
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

@router.post("/browser/browse")
async def browse_url(req: BrowseRequest):
    """Placeholder for browser control."""
    return {
        "success": True, 
        "message": f"Browser request for {req.url} received."
    }

# --- Desktop Management ---

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


# ─── Voice Transcription ─────────────────────────────────────────────────────

@router.post("/voice/transcribe")
async def transcribe_voice(file: UploadFile = File(...)):
    """
    Transcribe a recorded audio file using faster-whisper.
    Falls back with a clear error if faster-whisper is not installed.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="faster-whisper is not installed. Run: pip install faster-whisper"
        )

    # Save uploaded audio to a temp file
    suffix = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        logger.info(f"Transcribing voice file: {tmp_path}")
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(tmp_path, beam_size=5)
        text = " ".join(seg.text.strip() for seg in segments).strip()
        logger.info(f"Transcription result: {text}")
        return {"text": text}
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
