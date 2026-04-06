from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import json
import logging
import os
import tempfile
import base64
from typing import Optional
from core.agent import run_agent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["voice"])

# ─── TTS Utility (Windows SAPI5) ───────────────────────────────────────────

def speak_text_sapi5(text: str):
    """Offline TTS using Windows native SAPI5."""
    try:
        import win32com.client
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        # Find a good voice (optional, defaults to system voice)
        speaker.Speak(text)
        return True
    except Exception as e:
        logger.error(f"SAPI5 TTS Error: {e}")
        return False

# ─── STT Utility (Whisper) ────────────────────────────────────────────────

_whisper_model = None

def get_whisper():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
    return _whisper_model

async def transcribe_buffer(audio_data: bytes):
    model = get_whisper()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(audio_data)
        tmp_path = tmp.name
    
    try:
        segments, _ = await asyncio.to_thread(model.transcribe, tmp_path, language="en")
        text = " ".join(s.text.strip() for s in segments).strip()
        return text
    finally:
        os.unlink(tmp_path)

# ─── WebSocket Handler ───────────────────────────────────────────────────

@router.websocket("/ws/voice")
async def websocket_voice_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Voice WebSocket Accepted")
    
    audio_buffer = bytearray()
    
    try:
        while True:
            data = await websocket.receive()
            
            if "bytes" in data:
                audio_buffer.extend(data["bytes"])
            
            elif "text" in data:
                payload = json.loads(data["text"])
                action = payload.get("action")
                
                if action == "process":
                    # Process the accumulated audio buffer
                    if len(audio_buffer) == 0:
                        await websocket.send_json({"type": "error", "message": "No audio data received"})
                        continue
                        
                    task_id = payload.get("task_id", "voice_task")
                    await websocket.send_json({"type": "status", "state": "transcribing"})
                    
                    text = await transcribe_buffer(bytes(audio_buffer))
                    audio_buffer = bytearray() # Clear buffer
                    
                    if not text:
                        await websocket.send_json({"type": "status", "state": "listening", "message": "No speech detected"})
                        continue
                        
                    await websocket.send_json({"type": "transcription", "text": text})
                    await websocket.send_json({"type": "status", "state": "thinking"})
                    
                    # Run Agent
                    response = await run_agent(text, task_id=task_id)
                    result_text = response.get("steps", [{}])[0].get("content", "I am sorry, I encountered an error.")
                    
                    await websocket.send_json({"type": "response", "text": result_text})
                    await websocket.send_json({"type": "status", "state": "speaking"})
                    
                    # TTS (Offline SAPI5)
                    # Note: SAPI5 Speak is synchronous, so we run it in a thread
                    success = await asyncio.to_thread(speak_text_sapi5, result_text)
                    
                    await websocket.send_json({"type": "status", "state": "listening"})
                
                elif action == "clear":
                    audio_buffer = bytearray()
                    await websocket.send_json({"type": "status", "state": "listening"})

    except WebSocketDisconnect:
        logger.info("Voice WebSocket Disconnected")
    except Exception as e:
        logger.error(f"Voice WebSocket Error: {e}")
        await websocket.send_json({"type": "error", "message": str(e)})
