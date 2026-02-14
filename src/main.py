"""
This is the main entry point of the KIS Trading System.
It initializes authentication, WebSocket connections, and the interactive menu.

Startup order:
1. Telegram auto-init (for alert receiving)
2. Event Viewer auto-spawn
3. Super Menu display
"""
import logging
import os
import re
import sys
import time
import shutil
import threading
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

# Force-disable any global requests-cache to prevent SQLite multi-thread errors
try:
    import requests_cache
    if requests_cache.is_installed():
        requests_cache.uninstall_cache()
except ImportError:
    pass

# Import core modules
import trading_config
import state.market_state as trading_state
import display
from kis import event_pipe


class TradingSystem:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.logs_dir = self._get_logs_dir()
        self.log_file = self._get_log_file_path()
        self.shutdown_event = threading.Event()

    def _get_logs_dir(self):
        # If running from src/, logs should be in project root
        if os.path.basename(self.base_dir) == "src":
            return os.path.join(os.path.dirname(self.base_dir), "logs")
        return os.path.join(self.base_dir, "logs")

    def _get_log_file_path(self):
        if os.path.basename(self.base_dir) == "src":
            return os.path.join(os.path.dirname(self.base_dir), "WebSocket_latest.log")
        return os.path.join(self.base_dir, "WebSocket_latest.log")

    def setup_logging(self):
        """Configures system-wide logging with rotation."""
        if not os.path.exists(self.logs_dir):
            os.makedirs(self.logs_dir)

        # Archive old log if exists
        rotation_msgs = self._archive_existing_log()
        
        # Share log path with display module
        display.log_file_path = self.log_file

        # Reset root logger
        root_logger = logging.getLogger()
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)

        # Configure TimedRotatingFileHandler
        file_handler = TimedRotatingFileHandler(
            self.log_file, when='H', interval=6, encoding='utf-8'
        )
        file_handler.suffix = "%y_%m_%d_%H_%M_%S"
        file_handler.namer = self._log_namer
        file_handler.rotator = self._log_rotator
        
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        file_handler.setFormatter(formatter)
        
        # Console output
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)

        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(stream_handler)

        # Remove stream handler so future logs only go to file (unless critical)
        root_logger.removeHandler(stream_handler)

        # Suppress noisy libraries
        for lib in ["httpx", "httpcore", "telegram", "apscheduler", "websockets", "asyncio"]:
            logging.getLogger(lib).setLevel(logging.INFO)

        # Log rotation messages
        for msg in rotation_msgs:
            logging.info(msg)
            
        logging.info(f"[System] Logging initialized. Log file: {os.path.basename(self.log_file)}")

    def _archive_existing_log(self):
        """Moves existing WebSocket_latest.log to logs/ directory with timestamp."""
        msgs = []
        if not os.path.exists(self.log_file):
            msgs.append(f"[LogRotation] Fresh session. No existing log file found.")
            return msgs

        old_ts = ""
        try:
            with open(self.log_file, "r", encoding="utf-8-sig") as f:
                for _ in range(20):
                    line = f.readline()
                    if not line: break
                    match = re.search(r"(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})", line)
                    if match:
                        y, m, d, hh, mm, ss = match.groups()
                        old_ts = f"{y[2:]}_{m}_{d}_{hh}_{mm}_{ss}"
                        break
        except Exception as e:
            msgs.append(f"[LogRotation] Warning: Could not read timestamp: {e}")

        if not old_ts:
            try:
                mtime = os.path.getmtime(self.log_file)
                old_ts = datetime.fromtimestamp(mtime).strftime("%y_%m_%d_%H_%M_%S")
            except:
                old_ts = datetime.now().strftime("%y_%m_%d_%H_%M_%S")

        archive_name = os.path.join(self.logs_dir, f"WebSocket_{old_ts}.log")
        if os.path.exists(archive_name):
            archive_name = archive_name.replace(".log", f"_{int(datetime.now().timestamp())}.log")

        try:
            shutil.move(self.log_file, archive_name)
            msgs.append(f"[LogRotation] Archived: {os.path.basename(archive_name)}")
        except Exception as e:
            msgs.append(f"[LogRotation] Archive error: {e}")

        return msgs

    def _log_namer(self, default_name):
        base = os.path.basename(default_name)
        parts = base.split('.')
        if len(parts) >= 3:
            timestamp = parts[-1]
            return os.path.join(self.logs_dir, f"WebSocket_{timestamp}.log")
        return os.path.join(self.logs_dir, base)

    def _log_rotator(self, source, dest):
        if os.path.exists(source):
            try:
                shutil.move(source, dest)
            except Exception as e:
                print(f"[LogRotation] Runtime rotation error: {e}")

    def initialize_telegram(self):
        """Initializes the Telegram bot."""
        print("[Startup] Step 1: Initializing Telegram Bot...")
        try:
            from state.system_state import ThreadStatus, update_telegram_state
            from telegram_bot.telegram_bot import initialize_telegram

            update_telegram_state(thread_status=ThreadStatus.STARTING)
            if initialize_telegram():
                update_telegram_state(thread_status=ThreadStatus.RUNNING, bot_connected=True)
                logging.info("[Startup] Telegram Bot initialized")
                print("[Startup] ✓ Telegram Bot initialized")
            else:
                update_telegram_state(thread_status=ThreadStatus.ERROR, last_error="Failed")
                logging.warning("[Startup] Telegram init failed")
                print("[Startup] ✗ Telegram init failed (continuing...)")
        except Exception as e:
            logging.warning(f"[Startup] Telegram error: {e}")
            print(f"[Startup] ✗ Telegram error: {str(e)[:50]} (continuing...)")

    def initialize_kis(self):
        """Initializes KIS API connection, authentication, and WebSocket."""
        print("[Startup] Step 2: Initializing KIS API...")
        try:
            from kis.kis_thread import (
                start_kis_thread, is_kis_thread_running,
                request_kis_auth, request_kis_ws_auth, wait_for_response,
                initialize_websocket_and_pipe
            )

            # Start KIS thread
            if not is_kis_thread_running():
                if start_kis_thread():
                    logging.info("[Startup] KIS Thread started")
                    print("[Startup] ✓ KIS Thread started")
                else:
                    logging.error("[Startup] Failed to start KIS Thread")
                    print("[Startup] ✗ KIS Thread failed")
                    return False

            time.sleep(0.5)

            # REST API Auth
            print("[Startup]   - Authenticating REST API...")
            auth_id = request_kis_auth()
            response = wait_for_response(auth_id, timeout=30.0)
            if response and response.success:
                logging.info("[Startup] KIS REST API authenticated")
                print("[Startup] ✓ REST API authenticated")
            else:
                error = response.error if response else "Timeout"
                logging.error(f"[Startup] REST Auth failed: {error}")
                print(f"[Startup] ✗ REST Auth failed: {error}")

            # WebSocket Auth
            print("[Startup]   - Authenticating WebSocket...")
            ws_auth_id = request_kis_ws_auth()
            response = wait_for_response(ws_auth_id, timeout=30.0)
            if response and response.success:
                logging.info("[Startup] KIS WebSocket authenticated")
                print("[Startup] ✓ WebSocket authenticated")
            else:
                error = response.error if response else "Timeout"
                logging.error(f"[Startup] WS Auth failed: {error}")
                print(f"[Startup] ✗ WS Auth failed: {error}")

            # Initialize WebSocket & Pipe
            print("[Startup]   - Starting WebSocket connection...")
            if event_pipe.create_pipe_server():
                logging.info("[Startup] Pipe server created")
                self._start_pipe_client_waiter()

            if initialize_websocket_and_pipe():
                logging.info("[Startup] KIS fully initialized")
                print("[Startup] ✓ KIS fully initialized")
            else:
                logging.warning("[Startup] KIS init had issues")
                print("[Startup] ✗ KIS init had issues")

            # Sync orders
            print("[Startup]   - Syncing open orders...")
            from kis.wrapper import sync_open_orders
            sync_open_orders()
            logging.info("[Startup] Orders synced")
            print("[Startup] ✓ Orders synced")
            return True

        except Exception as e:
            logging.error(f"[Startup] KIS error: {e}")
            print(f"[Startup] ✗ KIS error: {str(e)[:50]}")
            return False

    def _start_pipe_client_waiter(self):
        def wait_client():
            if event_pipe.wait_for_client():
                event_pipe.start_writer_thread()
        client_thread = threading.Thread(target=wait_client, daemon=True)
        client_thread.start()

    def start_scheduler(self):
        """Starts the scheduler service."""
        print("[Startup] Step 3: Starting Scheduler Service...")
        try:
            from scheduler.scheduler import start_scheduler
            start_scheduler()
            print("[Startup] ✓ Scheduler started")
        except Exception as e:
            print(f"[Startup] ✗ Scheduler error: {e}")
            logging.error(f"[Startup] Scheduler error: {e}")

    def start_web_server(self):
        """Starts the Web Event Viewer in a background thread."""
        print("")
        print("[Startup] Step 4: Starting Web Event Viewer...")
        print("[Startup] Access at: https://<server-ip>:8080")
        print("")

        try:
            from web_server import start_web_server
            web_thread = threading.Thread(
                target=start_web_server, 
                kwargs={"host": "0.0.0.0", "port": 8080}, 
                daemon=True
            )
            web_thread.start()
            print("[Startup] ✓ Web Event Viewer started in background")
        except Exception as e:
            logging.error(f"[System] Web server error: {e}")
            print(f"[Error] Failed to start web server: {e}")

    def shutdown(self):
        """Gracefully shuts down all subsystems."""
        print("\n[System] Shutting down...")
        
        try:
            from kis.kis_thread import stop_kis_thread
            stop_kis_thread()
            print("[System] KIS thread stopped")
        except Exception as e:
            logging.error(f"Error stopping KIS thread: {e}")

        try:
            from telegram_bot.telegram_bot import shutdown_telegram
            shutdown_telegram()
            print("[System] Telegram shutdown signal sent")
        except Exception as e:
            logging.error(f"Error stopping Telegram: {e}")

        print("[System] Goodbye!")

    def run(self):
        """Main execution flow."""
        self.setup_logging()

        print("=== KIS Real-time Trading System ===")
        print("")
        print("[Startup] System initializing...")
        print("")

        self.initialize_telegram()
        time.sleep(0.5)
        
        self.initialize_kis()
        time.sleep(0.5)
        
        self.start_scheduler()
        
        self.start_web_server()
        time.sleep(1)

        print("")
        print("[Startup] Step 5: System is ready. Running in daemon mode.")
        print("[System] Logs are being piped to stdout/file. Use 'docker logs -f' to view.")
        print("")

        try:
            while not self.shutdown_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[Shutdown] Keyboard Interrupt")
        except Exception as e:
            print(f"[Error] System crashed: {e}")
            logging.error(f"[System] Crash: {e}", exc_info=True)
        finally:
            self.shutdown()


if __name__ == "__main__":
    app = TradingSystem()
    app.run()
