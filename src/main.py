# -*- coding: utf-8 -*-
"""
Main Trading System Entry Point

Initializes and orchestrates all sub-systems (KIS, Telegram, Scheduler, Web).
"""
import os
import sys
import time
import threading
import logging

# Force-disable any global requests-cache to prevent SQLite multi-thread errors
try:
    import requests_cache
    if requests_cache.is_installed():
        requests_cache.uninstall_cache()
except ImportError:
    pass

# Import Core Modules
from core import trading_config
import state.market_state as trading_state
from core import display
from utils.logger import LogManager
from kis import event_pipe

class TradingSystem:
    """Main application class for the KIS Trading System."""

    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.shutdown_event = threading.Event()

    def setup_logging(self):
        """Configures system-wide logging via LogManager."""
        log_file = LogManager.setup(self.base_dir)
        display.log_file_path = log_file

    def initialize_telegram(self):
        """Initializes the Telegram bot thread."""
        print("[Startup] Step 1: Initializing Telegram Bot...")
        from state.system_state import ThreadStatus, update_telegram_state
        from telegram_bot.telegram_bot import initialize_telegram

        update_telegram_state(thread_status=ThreadStatus.STARTING)
        if initialize_telegram():
            update_telegram_state(thread_status=ThreadStatus.RUNNING, bot_connected=True)
            logging.info("[Startup] Telegram Bot initialized")
            print("[Startup] ✓ Telegram Bot initialized")
        else:
            update_telegram_state(thread_status=ThreadStatus.ERROR, last_error="Failed")
            print("[Startup] ✗ Telegram init failed (continuing...)")

    def initialize_kis(self):
        """Initializes KIS API and WebSocket connection."""
        print("[Startup] Step 2: Initializing KIS API...")
        try:
            from kis.kis_thread import (
                start_kis_thread, is_kis_thread_running,
                request_kis_auth, request_kis_ws_auth, wait_for_response,
                initialize_websocket_and_pipe
            )

            if not is_kis_thread_running():
                if start_kis_thread():
                    print("[Startup] ✓ KIS Thread started")
                else:
                    print("[Startup] ✗ KIS Thread failed")
                    return False

            time.sleep(0.5)

            # REST & WS Auth
            auth_id = request_kis_auth()
            if wait_for_response(auth_id, timeout=30.0).success:
                print("[Startup] ✓ REST API authenticated")
            
            ws_auth_id = request_kis_ws_auth()
            if wait_for_response(ws_auth_id, timeout=30.0).success:
                print("[Startup] ✓ WebSocket authenticated")

            # Pipe Server & WS Init
            if event_pipe.create_pipe_server():
                def wait_client():
                    if event_pipe.wait_for_client(): event_pipe.start_writer_thread()
                threading.Thread(target=wait_client, daemon=True).start()

            if initialize_websocket_and_pipe():
                print("[Startup] ✓ KIS fully initialized")
            
            from kis.wrapper import sync_open_orders
            sync_open_orders()
            print("[Startup] ✓ Orders synced")
            return True
        except Exception as e:
            logging.error(f"[Startup] KIS error: {e}")
            return False

    def start_scheduler(self):
        """Starts the background task scheduler."""
        print("[Startup] Step 3: Starting Scheduler Service...")
        try:
            from scheduler.scheduler import start_scheduler
            start_scheduler()
            print("[Startup] ✓ Scheduler started")
        except Exception as e:
            logging.error(f"[Startup] Scheduler error: {e}")

    def start_web_server(self):
        """Starts the Web Event Viewer dashboard."""
        print("[Startup] Step 4: Starting Web Event Viewer...")
        from core.constants import DEFAULT_WEB_PORT, DEFAULT_HOST
        try:
            from core.web_server import start_web_server
            threading.Thread(target=start_web_server, kwargs={"host": DEFAULT_HOST, "port": DEFAULT_WEB_PORT}, daemon=True).start()
            print("[Startup] ✓ Web Event Viewer started in background")
        except Exception:
            logging.exception("[Startup] Web server failed to start")

    def shutdown(self):
        """Gracefully shuts down all systems."""
        print("\n[System] Shutting down...")
        try:
            from kis.kis_thread import stop_kis_thread
            stop_kis_thread()
        except: pass
        try:
            from telegram_bot.telegram_bot import shutdown_telegram
            shutdown_telegram()
        except: pass
        print("[System] Goodbye!")

    def run(self):
        """Main execution loop."""
        self.setup_logging()
        print("=== KIS Real-time Trading System ===\n")
        
        self.initialize_telegram()
        time.sleep(0.5)
        self.initialize_kis()
        time.sleep(0.5)
        self.start_scheduler()
        self.start_web_server()
        
        print("\n[Startup] Step 5: System is ready. Running in daemon mode.")
        try:
            while not self.shutdown_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[Shutdown] Keyboard Interrupt")
        finally:
            self.shutdown()

if __name__ == "__main__":
    app = TradingSystem()
    app.run()
