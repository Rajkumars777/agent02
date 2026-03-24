from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict, Any
import json
import time
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["events"])


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, task_id: str, websocket: WebSocket):
        await websocket.accept()
        if task_id not in self.active_connections:
            self.active_connections[task_id] = []
        self.active_connections[task_id].append(websocket)
        logger.info(f"WS: Client connected to task {task_id}")

    def disconnect(self, task_id: str, websocket: WebSocket):
        if task_id in self.active_connections:
            try:
                self.active_connections[task_id].remove(websocket)
            except ValueError:
                pass  # Already removed — safe to ignore
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]
        logger.info(f"WS: Client disconnected from task {task_id}")

    async def send_event(self, task_id: str, event_type: str, data: Any):
        if task_id in self.active_connections:
            message = {
                "task_id": task_id,
                "type": event_type,
                "data": data,
                "timestamp": time.time(),  # Use time.time() — no deprecated event loop access
            }
            dead_connections: List[WebSocket] = []
            for connection in list(self.active_connections.get(task_id, [])):
                try:
                    await connection.send_text(json.dumps(message))
                except Exception as e:
                    logger.warning(f"WS: Error sending to task {task_id}: {e}")
                    dead_connections.append(connection)

            # Clean up dead connections
            for dead in dead_connections:
                try:
                    self.active_connections[task_id].remove(dead)
                except ValueError:
                    pass
            if task_id in self.active_connections and not self.active_connections[task_id]:
                del self.active_connections[task_id]


manager = ConnectionManager()


@router.websocket("/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    await manager.connect(task_id, websocket)
    try:
        while True:
            # Keep connection alive; handle optional client-to-server messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(task_id, websocket)
    except Exception as e:
        logger.warning(f"WS: Unexpected error for task {task_id}: {e}")
        manager.disconnect(task_id, websocket)


async def emit_event(task_id: str, event_type: str, data: Any):
    """Utility to emit events from anywhere in the backend."""
    await manager.send_event(task_id, event_type, data)
