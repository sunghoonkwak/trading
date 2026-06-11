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
import requests

# Global monkey-patch to enforce a 30-second timeout on all requests
_original_request = requests.api.request
def _request_with_timeout(method, url, **kwargs):
    kwargs.setdefault('timeout', 30.0)
    return _original_request(method, url, **kwargs)
requests.api.request = _request_with_timeout

_original_session_request = requests.Session.request
def _session_request_with_timeout(self, method, url, **kwargs):
    kwargs.setdefault('timeout', 30.0)
    return _original_session_request(self, method, url, **kwargs)
requests.Session.request = _session_request_with_timeout

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
from core import event_pipe
from core import lock_manager

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
            from broker.kis_worker import (
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
            auth_response = wait_for_response(auth_id, timeout=30.0)
            if not auth_response or not auth_response.success:
                error = auth_response.error if auth_response else "timeout"
                logging.error(f"[Startup] REST API authentication failed: {error}")
                print("[Startup] ✗ REST API authentication failed")
                return False
            print("[Startup] ✓ REST API authenticated")

            ws_auth_id = request_kis_ws_auth()
            ws_auth_response = wait_for_response(ws_auth_id, timeout=30.0)
            if not ws_auth_response or not ws_auth_response.success:
                error = ws_auth_response.error if ws_auth_response else "timeout"
                logging.error(f"[Startup] WebSocket authentication failed: {error}")
                print("[Startup] ✗ WebSocket authentication failed")
                return False
            print("[Startup] ✓ WebSocket authenticated")

            # Pipe Server & WS Init
            if event_pipe.create_pipe_server():
                def wait_client():
                    if event_pipe.wait_for_client(): event_pipe.start_writer_thread()
                threading.Thread(target=wait_client, daemon=True).start()

            if not initialize_websocket_and_pipe():
                logging.error("[Startup] WebSocket and event pipe initialization failed")
                print("[Startup] ✗ KIS WebSocket initialization failed")
                return False
            print("[Startup] ✓ KIS fully initialized")

            from broker.order_admin import sync_open_orders
            sync_open_orders()
            print("[Startup] ✓ Orders synced")
            return True
        except Exception as e:
            logging.error(f"[Startup] KIS error: {e}")
            return False

    def initialize_toss(self):
        """Initializes Toss access token for today's trading session."""
        print("[Startup] Step 3: Initializing Toss API...")
        try:
            from toss.auth import ensure_daily_token

            token_path = ensure_daily_token()
            logging.info(f"[Startup] Toss token ready: {token_path}")
            print("[Startup] ✓ Toss API token ready")
            return True
        except Exception as e:
            logging.error(f"[Startup] Toss error: {e}")
            print("[Startup] ✗ Toss API initialization failed")
            return False

    def start_scheduler(self):
        """Starts the background task scheduler."""
        print("[Startup] Step 4: Starting Scheduler Service...")
        try:
            from scheduler.scheduler import start_scheduler
            start_scheduler()
            print("[Startup] ✓ Scheduler started")
        except Exception as e:
            logging.error(f"[Startup] Scheduler error: {e}")

    def start_web_server(self):
        """Starts the Web Event Viewer dashboard."""
        print("[Startup] Step 5: Starting Web Event Viewer...")
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
            from broker.kis_worker import stop_kis_thread
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

        # Ensure the script is only run within a Docker container
        if os.environ.get('ENV_MODE') != 'docker':
            print("\n[ERROR] This application must be run using Docker (docker-compose).")
            print("Direct execution of src/main.py on the host environment is strictly prohibited to prevent conflicts.")
            sys.exit(1)

        # Lock Check
        if not lock_manager.acquire_lock(self.base_dir):
            print("\n[ERROR] Another instance is already running!")
            print("Please stop the existing process (or Docker container) before starting a new one.\n")
            sys.exit(1)

        self.initialize_telegram()
        time.sleep(0.5)
        if not self.initialize_kis():
            logging.critical("[Startup] KIS initialization failed; refusing to start scheduler/web services")
            print("\n[ERROR] KIS initialization failed. Scheduler and web services will not start.")
            self.shutdown()
            sys.exit(1)
        time.sleep(0.5)
        if not self.initialize_toss():
            logging.critical("[Startup] Toss initialization failed; refusing to start scheduler/web services")
            print("\n[ERROR] Toss initialization failed. Scheduler and web services will not start.")
            self.shutdown()
            sys.exit(1)
        time.sleep(0.5)
        self.start_scheduler()
        self.start_web_server()

        print("\n[Startup] Step 6: System is ready. Running in daemon mode.")
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
