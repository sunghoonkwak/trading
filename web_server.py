"""
Web Server Module - Simplified Event Viewer for trading system.
Only provides WebSocket for real-time event streaming, no REST API control.
"""
import os
import sys
import asyncio
import logging
from datetime import datetime
from typing import Set, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class ConnectionManager:
    """Manages WebSocket connections for broadcasting events."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        logging.info(f"[WebServer] Client connected. Total: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            self.active_connections.discard(websocket)
        logging.info(f"[WebServer] Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        """Broadcast message to all connected clients."""
        if not self.active_connections:
            return
        async with self._lock:
            disconnected = []
            for connection in self.active_connections:
                try:
                    await connection.send_text(message)
                except Exception:
                    disconnected.append(connection)
            for conn in disconnected:
                self.active_connections.discard(conn)


manager = ConnectionManager()

# Event loop reference for thread-safe broadcasting
_event_loop: Optional[asyncio.AbstractEventLoop] = None


def _broadcast_callback(msg_type: str, message: str):
    """Callback for event_pipe to broadcast messages to web clients."""
    global _event_loop
    if _event_loop is None:
        return
    try:
        data = f'{{"type":"{msg_type}","data":"{message.replace(chr(34), chr(39))}","time":"{datetime.now().strftime("%H:%M:%S")}"}}'
        asyncio.run_coroutine_threadsafe(manager.broadcast(data), _event_loop)
    except Exception as e:
        logging.error(f"[WebServer] Broadcast error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global _event_loop

    # Startup
    _event_loop = asyncio.get_running_loop()

    # Register broadcast callback with event_pipe
    try:
        from kis import event_pipe
        event_pipe.set_web_broadcast_callback(_broadcast_callback)
        logging.info("[WebServer] Registered web broadcast callback")
    except Exception as e:
        logging.warning(f"[WebServer] Could not register callback: {e}")

    yield

    # Shutdown
    _event_loop = None


app = FastAPI(title="Trading Event Viewer", lifespan=lifespan)

# Mount static files
web_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
static_dir = os.path.join(web_dir, "static")

if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def get_index():
    """Serve main event viewer page."""
    index_path = os.path.join(web_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    return {"error": "index.html not found"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time event streaming."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text('{"type":"SYS","data":"pong"}')
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logging.error(f"[WebServer] WebSocket error: {e}")
        await manager.disconnect(websocket)


def start_web_server(host: str = "0.0.0.0", port: int = 8080):
    """Start the web server with logging redirected to file."""
    # Configure uvicorn to log to the same file as main app
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["handlers"]["default"]["stream"] = "ext://sys.stdout"
    log_config["handlers"]["access"]["stream"] = "ext://sys.stdout"

    logging.info(f"[WebServer] Starting on http://{host}:{port}")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="warning",  # Reduce HTTP log noise
        access_log=False      # Disable access logging to console
    )


if __name__ == "__main__":
    start_web_server()
