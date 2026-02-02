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
            elif data == "sync_orders":
                # Sync open orders on client request
                await sync_orders_to_client(websocket)
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logging.error(f"[WebServer] WebSocket error: {e}")
        await manager.disconnect(websocket)


async def sync_orders_to_client(websocket: WebSocket):
    """Fetch and send open orders to a specific client."""
    try:
        loop = asyncio.get_running_loop()
        orders_data = await loop.run_in_executor(None, _fetch_orders_for_sync)
        for order_msg in orders_data:
            await websocket.send_text(order_msg)
    except Exception as e:
        logging.error(f"[WebServer] Order sync error: {e}")


def _fetch_orders_for_sync():
    """Fetch open orders and format as WebSocket messages."""
    messages = []
    try:
        from menu.handle_manage_orders import fetch_open_orders
        import trading_config
        from utils import get_fixed_width
        from datetime import datetime

        df, num_us, num_kr = fetch_open_orders()

        if df.empty:
            return messages

        for _, row in df.iterrows():
            market = row.get('_market', 'US')
            row_lower = {k.lower(): v for k, v in row.items()}
            odno = row_lower.get('odno', row_lower.get('ord_no', 'Unknown'))
            pdno = row_lower.get('pdno', row_lower.get('stck_shrn_iscd', 'Unknown'))
            api_name = row_lower.get('prdt_name', row_lower.get('stck_nm', row_lower.get('stck_nm40', 'Unknown')))

            stock_info = trading_config.get_stock_info(pdno)
            display_name = stock_info.get('name', api_name)
            fixed_name = get_fixed_width(display_name, 20)

            if market == "KR":
                side = "Buy" if row_lower.get('sll_buy_dvsn_cd') == '02' else "Sell"
                price = str(int(float(row_lower.get('ord_unpr', '0'))))
                qty = str(row_lower.get('psbl_qty', 0))
            else:
                side_text = row_lower.get('sll_buy_dvsn_cd_name', row_lower.get('sll_buy_dvsn_name', '')).strip()
                if not side_text or side_text in ['?', 'nan', 'None', '']:
                    side = "Buy" if row_lower.get('sll_buy_dvsn_cd') == '02' else "Sell"
                else:
                    side = side_text

                p_val = row_lower.get('ft_ord_unpr3', row_lower.get('ft_ord_unpr4', row_lower.get('ovrs_ord_unpr', row_lower.get('ord_unpr', '0'))))
                price = f"${float(p_val):,.2f}" if float(p_val) > 0 else "Market"
                q_val = row_lower.get('nccs_qty', row_lower.get('ft_ord_qty4', row_lower.get('ord_qty', 0)))
                qty = str(int(float(q_val)))

            order_msg = f"{fixed_name}|{pdno}|{side}|{qty}|{price}|PLACED|{odno}"
            # Use actual order time if available
            raw_time = row_lower.get('ord_tmd', '')
            if raw_time and len(raw_time) == 6:
                time_str = f"{raw_time[:2]}:{raw_time[2:4]}:{raw_time[4:]}"
            else:
                time_str = datetime.now().strftime("%H:%M:%S")

            msg = f'{{"type":"ODR","data":"{order_msg}","time":"{time_str}"}}'
            messages.append(msg)

    except Exception as e:
        logging.error(f"[WebServer] Failed to fetch orders: {e}")

    return messages


def start_web_server(host: str = "0.0.0.0", port: int = 8080, use_ssl: bool = True):
    """Start the web server with optional HTTPS support."""
    # Configure uvicorn to log to the same file as main app
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["handlers"]["default"]["stream"] = "ext://sys.stdout"
    log_config["handlers"]["access"]["stream"] = "ext://sys.stdout"

    # SSL certificate paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cert_file = os.path.join(base_dir, "certs", "cert.pem")
    key_file = os.path.join(base_dir, "certs", "key.pem")

    ssl_enabled = use_ssl and os.path.exists(cert_file) and os.path.exists(key_file)
    protocol = "https" if ssl_enabled else "http"
    logging.info(f"[WebServer] Starting on {protocol}://{host}:{port}")

    if ssl_enabled:
        uvicorn.run(
            app,
            host=host,
            port=port,
            ssl_certfile=cert_file,
            ssl_keyfile=key_file,
            log_level="warning",
            access_log=False
        )
    else:
        if use_ssl:
            logging.warning("[WebServer] SSL requested but certs not found, falling back to HTTP")
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="warning",
            access_log=False
        )


if __name__ == "__main__":
    start_web_server()
