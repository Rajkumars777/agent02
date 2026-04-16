from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.agent import run_agent
from core.memory import memory_manager
import asyncio
from typing import Optional, Any
import uuid

router = APIRouter(prefix="/agent", tags=["agent"])

# Track active tasks for cancellation
active_tasks: dict[str, asyncio.Task] = {}
cancelled_tasks: set[str] = set()

class AgentRequest(BaseModel):
    input: str
    task_id: Optional[str] = None
    channel: Optional[str] = "nexus"
    sender: Optional[str] = "main"
    files: Optional[list[dict[str, Any]]] = None
    use_web: Optional[bool] = False

class CancelRequest(BaseModel):
    task_id: str

class ResumeRequest(BaseModel):
    task_id: str
    data: Any

@router.post("/chat")
async def chat_with_agent(request: AgentRequest):
    """Run the AI Agent with the given input. Returns execution steps."""
    task_id = request.task_id or str(uuid.uuid4())
    channel = request.channel or "nexus"
    sender = request.sender or "main"
    
    # Check if already cancelled before starting
    if task_id in cancelled_tasks:
        cancelled_tasks.discard(task_id)
        return {"cancelled": True, "task_id": task_id, "steps": []}
    
    try:
        # ✅ Track task for cancellation
        task = asyncio.create_task(run_agent(
            request.input, 
            task_id=task_id, 
            channel=channel, 
            sender=sender,
            files=request.files,
            use_web=request.use_web
        ))
        active_tasks[task_id] = task
        
        # Save to history
        memory_manager.add_to_history(request.input)
        
        response = await task
        
        # Check if cancelled during execution
        if task_id in cancelled_tasks:
            cancelled_tasks.discard(task_id)
            return {"cancelled": True, "task_id": task_id, "steps": []}
        
        response["task_id"] = task_id
        return response
    except asyncio.CancelledError:
        return {"cancelled": True, "task_id": task_id, "steps": []}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up active task tracking
        active_tasks.pop(task_id, None)
        # Clean up cancelled_tasks to prevent unbounded memory growth
        cancelled_tasks.discard(task_id)

@router.post("/cancel")
async def cancel_operation(request: CancelRequest):
    """Cancel an ongoing operation."""
    task_id = request.task_id
    cancelled_tasks.add(task_id)
    
    # Try to cancel the active task if it exists
    if task_id in active_tasks:
        task = active_tasks[task_id]
        task.cancel()
        del active_tasks[task_id]
        return {"success": True, "message": f"Task {task_id} cancelled"}
    
    return {"success": True, "message": f"Task {task_id} marked for cancellation"}

@router.post("/resume")
async def resume_operation(request: ResumeRequest):
    """Resume a browser task waiting for user input (credentials, etc.)."""
    from capabilities.browser_use_client import browser_client
    delivered = browser_client.provide_answer(request.task_id, str(request.data))
    return {
        "success": True,
        "delivered": delivered,
        "message": "Answer delivered to browser agent." if delivered else "No task was waiting.",
        "task_id": request.task_id
    }

@router.get("/status")
async def get_status():
    """Get agent status."""
    return {
        "active_tasks": len(active_tasks),
        "cancelled_tasks": len(cancelled_tasks)
    }

@router.get("/history")
async def get_history():
    """Get prompt history."""
    return {"history": memory_manager.get_history()}

@router.post("/history")
async def save_history(data: dict):
    """Save full prompt history."""
    history = data.get("history", [])
    memory_manager.save_history(history)
    return {"success": True}

@router.get("/folders")
async def get_folders():
    """Get foldered prompts."""
    return {"folders": memory_manager.get_folders()}

@router.post("/folders")
async def save_folders(data: dict):
    """Save foldered prompts."""
    folders = data.get("folders", [])
    memory_manager.save_folders(folders)
    return {"success": True}
