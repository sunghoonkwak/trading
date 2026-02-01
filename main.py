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
from datetime import datetime
import sys
import time
from logging.handlers import TimedRotatingFileHandler
import shutil
import threading


def archive_existing_log(latest_log, logs_dir):
    """
    Moves existing WebSocket_latest.log to logs/ directory with timestamp.
    Returns list of status messages.
    """
    msgs = []
    if not os.path.exists(latest_log):
        msgs.append(f"[LogRotation] Fresh session. No existing log file found.")
        return msgs

    old_ts = ""
    try:
        with open(latest_log, "r", encoding="utf-8-sig") as f:
            for _ in range(20):
                line = f.readline()
                if not line: break
                match = re.search(r"(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})", line)
                if match:
                    y, m, d, hh, mm, ss = match.groups()
                    old_ts = f"{y[2:]}_{m}_{d}_{hh}_{mm}_{ss}"
                    break
    except Exception as e:
        msgs.append(f"[LogRotation] Warning: Could not read timestamp from content: {e}")

    if not old_ts:
        try:
            mtime = os.path.getmtime(latest_log)
            old_ts = datetime.fromtimestamp(mtime).strftime("%y_%m_%d_%H_%M_%S")
        except:
            old_ts = datetime.now().strftime("%y_%m_%d_%H_%M_%S")

    # Archive to logs/ folder
    archive_name = os.path.join(logs_dir, f"WebSocket_{old_ts}.log")
    if os.path.exists(archive_name):
        archive_name = archive_name.replace(".log", f"_{int(datetime.now().timestamp())}.log")

    try:
        shutil.move(latest_log, archive_name)
        msgs.append(f"[LogRotation] Moved old log: WebSocket_latest.log -> logs/{os.path.basename(archive_name)}")
    except PermissionError:
        msgs.append(f"[LogRotation] Warning: {os.path.basename(latest_log)} is locked. Appending to existing file.")
    except Exception as e:
        msgs.append(f"[LogRotation] Error during move: {e}")

    return msgs

# Force-disable any global requests-cache to prevent SQLite multi-thread errors
try:
    import requests_cache
    if requests_cache.is_installed():
        requests_cache.uninstall_cache()
except ImportError:
    pass

# Import refactored modules
import trading_config
import trading_state
import display
from display import add_alert
from kis import event_pipe


if __name__ == "__main__":
    # [CRITICAL] Configure logging at the VERY TOP
    base_dir = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(base_dir, "logs")

    # Ensure logs directory exists
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    # Latest log in root, archived logs in logs/
    latest_log = os.path.join(base_dir, "WebSocket_latest.log")

    rotation_msgs = archive_existing_log(latest_log, logs_dir)
    log_file = latest_log
    display.log_file_path = log_file

    # Force reset root logger handlers
    root_logger = logging.getLogger()
    if root_logger.handlers:
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)

    # file_handler = logging.FileHandler(log_file, encoding='utf-8')
    # Use TimedRotatingFileHandler for 6-hour rotation
    file_handler = TimedRotatingFileHandler(
        log_file, when='H', interval=6, encoding='utf-8'
    )
    file_handler.suffix = "%y_%m_%d_%H_%M_%S"

    def log_namer(default_name):
        # Transform .../WebSocket_latest.log.26_01_04_22_00_00 -> .../logs/WebSocket_26_01_04_22_00_00.log
        base = os.path.basename(default_name)
        parts = base.split('.')
        # check if it matches the suffix format, usually it's appended
        # parts: ['WebSocket_latest', 'log', '26_01_04_22_00_00']
        if len(parts) >= 3:
            timestamp = parts[-1]
            return os.path.join(logs_dir, f"WebSocket_{timestamp}.log")
        return os.path.join(logs_dir, base)

    def log_rotator(source, dest):
        if os.path.exists(source):
            try:
                shutil.move(source, dest)
            except Exception as e:
                print(f"[LogRotation] Runtime rotation error: {e}")

    file_handler.namer = log_namer
    file_handler.rotator = log_rotator
    stream_handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)

    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)

    # Remove stream handler first, so rotation messages only go to file
    root_logger.removeHandler(stream_handler)

    # Suppress third-party libraries (Set to INFO as requested)
    for lib in ["httpx", "httpcore", "telegram", "apscheduler", "websockets", "asyncio"]:
        logging.getLogger(lib).setLevel(logging.INFO)

    for msg in rotation_msgs:
        logging.info(msg)

    logging.info(f"[System] Logging initialized. All system messages now directed to: {os.path.basename(log_file)}")

    print("=== KIS Real-time Trading System ===")
    print("")  # Blank line for separation

    # ============================================
    # Auto-initialize everything, then start Event Viewer server
    # ============================================
    print("[Startup] System initializing...")
    print("")

    # Step 1: Initialize Telegram
    print("[Startup] Step 1: Initializing Telegram Bot...")
    try:
        from thread_state import ThreadStatus, update_telegram_state
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

    time.sleep(0.5)

    # Step 2: Initialize KIS API
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

            import threading
            def wait_client():
                if event_pipe.wait_for_client():
                    event_pipe.start_writer_thread()
            client_thread = threading.Thread(target=wait_client, daemon=True)
            client_thread.start()

        if initialize_websocket_and_pipe():
            logging.info("[Startup] KIS fully initialized")
            print("[Startup] ✓ KIS fully initialized")
        else:
            logging.warning("[Startup] KIS init had issues")
            print("[Startup] ✗ KIS init had issues")

        # Sync orders
        print("[Startup]   - Syncing open orders...")
        from menu.handle_manage_orders import sync_open_orders
        sync_open_orders()
        logging.info("[Startup] Orders synced")
        print("[Startup] ✓ Orders synced")

    except Exception as e:
        logging.error(f"[Startup] KIS error: {e}")
        print(f"[Startup] ✗ KIS error: {str(e)[:50]}")

    time.sleep(0.5)

    # Step 3: Start Web Event Viewer
    print("")
    print("[Startup] Step 3: Starting Web Event Viewer...")
    print("[Startup] Access at: http://<server-ip>:8080")
    print("")

    try:
        from web_server import start_web_server
        # Run web server in background thread to not block the menu
        web_thread = threading.Thread(target=start_web_server, kwargs={"host": "0.0.0.0", "port": 8080}, daemon=True)
        web_thread.start()
        print("[Startup] ✓ Web Event Viewer started in background")
    except Exception as e:
        logging.error(f"[System] Web server error: {e}")
        print(f"[Error] Failed to start web server: {e}")

    time.sleep(1)

    # Step 4: Launch Super Menu
    print("")
    print("[Startup] Step 4: Starting Super Menu...")
    print("")

    # Step 4: Launch Trading Menu
    print("")
    print("[Startup] Step 4: Starting Trading Menu...")
    print("")

    try:
        from menu.menu import menu
        if os.environ.get("ENV_MODE") == "docker":
            print("[System] Docker mode detected. Running in daemon mode (no menu).")
            print("[System] Logs are being piped to stdout/file. Use 'docker logs -f' to view.")
            while True:
                time.sleep(3600)
        else:
            menu()
    except KeyboardInterrupt:
        print("\n[Shutdown] Keyboard Interrupt")
    except Exception as e:
        print(f"[Error] Menu crashed: {e}")
        logging.error(f"[System] Menu crash: {e}", exc_info=True)
    finally:
        # Shutdown sequence
        print("\n[System] Shutting down...")
        try:
            from kis.kis_thread import stop_kis_thread
            stop_kis_thread()
            print("[System] KIS thread stopped")
        except:
            pass

        try:
            from telegram_bot.telegram_bot import shutdown_telegram
            shutdown_telegram()
            print("[System] Telegram shutdown signal sent")
        except:
            pass

        print("[System] Goodbye!")
