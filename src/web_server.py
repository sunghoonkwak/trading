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

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import json
from pydantic import BaseModel

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
            # logging.debug("[WebServer] No active connections to broadcast")
            return
        async with self._lock:
            disconnected = []
            for connection in self.active_connections:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logging.warning(f"[WebServer] Broadcast failed for client: {e}")
                    disconnected.append(connection)
            for conn in disconnected:
                self.active_connections.discard(conn)


manager = ConnectionManager()

# Event loop reference for thread-safe broadcasting
_event_loop: Optional[asyncio.AbstractEventLoop] = None


def _broadcast_callback(msg_type: str, message: str, time_str: str = None):
    """Callback for event_pipe to broadcast messages to web clients."""
    global _event_loop
    if _event_loop is None:
        logging.error("[WebServer] Cannot broadcast: _event_loop is None")
        return
    try:
        final_time = time_str if time_str else datetime.now().strftime("%H:%M:%S")
        data = f'{{"type":"{msg_type}","data":"{message.replace(chr(34), chr(39))}","time":"{final_time}"}}'
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


class MemoDeleteRequest(BaseModel):
    date: str
    text: str


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serve favicon."""
    favicon_path = os.path.join(web_dir, "favicon.ico")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    return {"error": "favicon.ico not found"}


@app.get("/")
async def get_index():
    """Serve main event viewer page."""
    index_path = os.path.join(web_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    return {"error": "index.html not found"}


@app.get("/api/memos")
async def get_memos():
    """Fetch all memos from memo.json."""
    try:
        from data.config_manager import ConfigFile, load_json
        messages = load_json(ConfigFile.MEMO, default={})
        return messages
    except Exception as e:
        logging.error(f"[WebServer] Failed to fetch memos: {e}")
        return {"error": str(e)}


@app.post("/api/memos/delete")
async def delete_memo(request: MemoDeleteRequest):
    """Delete a specific memo."""
    try:
        from data.config_manager import ConfigFile, load_json, save_json
        messages = load_json(ConfigFile.MEMO, default={})

        date_key = request.date
        target_text = request.text

        if date_key in messages:
            # Filter out the exact message
            original_len = len(messages[date_key])
            messages[date_key] = [msg for msg in messages[date_key] if msg != target_text]

            if len(messages[date_key]) < original_len:
                if not messages[date_key]:  # Remove date key if empty
                    del messages[date_key]
                save_json(ConfigFile.MEMO, messages)
                return {"success": True, "message": "Memo deleted"}

        return {"success": False, "error": "Memo not found"}

    except Exception as e:
        logging.error(f"[WebServer] Failed to delete memo: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/holdings/{ticker}")
async def get_holdings_data(ticker: str):
    """Fetch holdings data for a specific ticker from portfolio.json."""
    try:
        # Use data_service to get portfolio data (handles caching and freshness)
        from data.data_service import get_portfolio_data

        loop = asyncio.get_running_loop()
        data_result = await loop.run_in_executor(None, get_portfolio_data)

        if data_result.get('error'):
             logging.warning(f"[WebServer] Portfolio data error: {data_result['error']}")
             # Return error immediately if data service fails, or return empty?
             # For now, let's proceed with empty list so at least 'found: False' is returned properly
             pass

        holdings = data_result.get('holdings', [])

        # Filter for the specific ticker (case-insensitive)
        matches = [h for h in holdings if h.get('ticker', '').upper() == ticker.upper()]

        if not matches:
            # Try case-insensitive name match as fallback
            matches = [h for h in holdings if h.get('name', '').upper() == ticker.upper()]

        if not matches:
            return {"found": False}

        # Calculate aggregates
        total_qty = sum(h.get('qty', 0) for h in matches)
        total_stk_eval = sum(h.get('cur_price', 0) * h.get('qty', 0) for h in matches)
        total_invest = sum(h.get('avg_price', 0) * h.get('qty', 0) for h in matches)

        avg_price = total_invest / total_qty if total_qty > 0 else 0
        cur_price = matches[0].get('cur_price', 0) # Assume same current price for same ticker

        pnl = total_stk_eval - total_invest
        pnl_rate = (pnl / total_invest * 100) if total_invest > 0 else 0

        # Determine currency (Heuristic: 6 digits = KRW, others = USD)
        currency = "KRW" if ticker.isdigit() and len(ticker) == 6 else "USD"

        # Map account IDs to names
        accounts_list = data_result.get('accounts', [])
        acc_map = {acc['id']: acc['name'] for acc in accounts_list}

        # Enrich matches with account names
        start_breakdown = []
        for m in matches:
            # Create a copy to avoid modifying original data if that matters (it stays in scope though)
            item = m.copy()
            acc_id = item.get('account_id')
            item['account_name'] = acc_map.get(acc_id, acc_id) # Fallback to ID if name not found
            start_breakdown.append(item)

        return {
            "found": True,
            "ticker": matches[0].get('ticker'),
            "name": matches[0].get('name'),
            "qty": total_qty,
            "avg_price": avg_price,
            "cur_price": cur_price,
            "total_val": total_stk_eval,
            "invested": total_invest,
            "pnl": pnl,
            "pnl_rate": pnl_rate,
            "currency": currency,
            "accounts": start_breakdown # Return enriched breakdown
        }

    except Exception as e:
        logging.error(f"[WebServer] detailed holdings error: {e}")
        return {"error": str(e)}


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
                from kis.wrapper import sync_open_orders
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, sync_open_orders)
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logging.error(f"[WebServer] WebSocket error: {e}")
        await manager.disconnect(websocket)


@app.post("/api/orders/{order_id}/cancel")
async def cancel_order(order_id: str):
    """Cancel an open order by its order ID."""
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, _cancel_order_sync, order_id)
        return result
    except Exception as e:
        logging.error(f"[WebServer] Cancel order error: {e}")
        return {"success": False, "error": str(e)}


@app.post("/api/trigger/portfolio")
async def trigger_portfolio_report(background_tasks: BackgroundTasks):
    """Trigger daily portfolio report manually."""
    try:
        from scheduler.scheduler_portfolio import run_daily_portfolio_report
        # Run in background to not block response
        background_tasks.add_task(run_daily_portfolio_report)
        return {"success": True, "message": "Portfolio report triggered"}
    except Exception as e:
        logging.error(f"[WebServer] Trigger portfolio error: {e}")
        return {"success": False, "error": str(e)}


@app.post("/api/trigger/order")
async def trigger_order_report(background_tasks: BackgroundTasks):
    """Trigger daily order report manually."""
    try:
        from scheduler.scheduler_order import run_daily_order_report
        # Run in background to not block response
        background_tasks.add_task(run_daily_order_report)
        return {"success": True, "message": "Order report triggered"}
    except Exception as e:
        logging.error(f"[WebServer] Trigger order error: {e}")
        return {"success": False, "error": str(e)}


def _cancel_order_sync(order_id: str):
    """Synchronously cancel an order by ID."""
    from kis.wrapper import fetch_open_orders, execute_manage_action

    try:
        df, _, _ = fetch_open_orders()
        if df.empty:
            return {"success": False, "error": "No open orders found"}

        # Find the order by ID
        target_order = None
        market = None
        for _, row in df.iterrows():
            row_lower = {k.lower(): v for k, v in row.items()}
            odno = row_lower.get('odno', row_lower.get('ord_no', ''))
            if str(odno) == str(order_id):
                target_order = row
                market = row.get('_market', 'US')
                break

        if target_order is None:
            return {"success": False, "error": f"Order {order_id} not found"}

        # Execute cancellation (action_type='2' means cancel)
        df_res, err_msg = execute_manage_action(market, '2', target_order, None)

        if err_msg:
            return {"success": False, "error": err_msg}

        # Check if cancellation was successful
        if not df_res.empty:
            cols = {c.lower(): c for c in df_res.columns}
            if 'odno' in cols or 'ord_no' in cols:
                return {"success": True, "message": "Order cancelled successfully"}

        return {"success": True, "message": "Cancel request submitted"}

    except Exception as e:
        logging.error(f"[WebServer] _cancel_order_sync error: {e}")
        return {"success": False, "error": str(e)}


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
