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

    rotation_msgs = []

    # Log Rotation Logic: Move old log from root to logs/ folder
    if os.path.exists(latest_log):
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
            rotation_msgs.append(f"[LogRotation] Warning: Could not read timestamp from content: {e}")

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
            import shutil
            shutil.move(latest_log, archive_name)
            rotation_msgs.append(f"[LogRotation] Moved old log: WebSocket_latest.log -> logs/{os.path.basename(archive_name)}")
        except PermissionError:
            rotation_msgs.append(f"[LogRotation] Warning: {os.path.basename(latest_log)} is locked. Appending to existing file.")
        except Exception as e:
            rotation_msgs.append(f"[LogRotation] Error during move: {e}")
    else:
        rotation_msgs.append(f"[LogRotation] Fresh session. No existing log file found.")

    log_file = latest_log
    display.log_file_path = log_file

    # Force reset root logger handlers
    root_logger = logging.getLogger()
    if root_logger.handlers:
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    stream_handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)

    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)

    # Remove stream handler first, so rotation messages only go to file
    root_logger.removeHandler(stream_handler)

    for msg in rotation_msgs:
        logging.info(msg)

    logging.info(f"[System] Logging initialized. All system messages now directed to: {os.path.basename(log_file)}")

    print("=== KIS Real-time Trading System ===")
    print("")  # Blank line for separation

    # ============================================
    # Step 1: Auto-initialize Telegram (for alerts)
    # ============================================
    print("[Startup] Step 1: Initializing Telegram Bot...")
    try:
        from thread_state import ThreadStatus, update_telegram_state
        from telegram_bot.telegram_bot import initialize_telegram

        update_telegram_state(thread_status=ThreadStatus.STARTING)
        if initialize_telegram():
            update_telegram_state(thread_status=ThreadStatus.RUNNING, bot_connected=True)
            add_alert("[Startup] Telegram Bot initialized", "SUCCESS")
        else:
            update_telegram_state(thread_status=ThreadStatus.ERROR, last_error="Failed")
            add_alert("[Startup] Telegram init failed (continuing...)", "WARNING")
    except Exception as e:
        add_alert(f"[Startup] Telegram error: {str(e)[:50]} (continuing...)", "WARNING")

    time.sleep(0.5)

    # ============================================
    # Step 2: Auto-spawn Event Viewer
    # ============================================
    print("[Startup] Step 2: Spawning Event Viewer...")
    try:
        # Create pipe server first
        if event_pipe.create_pipe_server():
            add_alert("[Startup] Pipe server created", "SUCCESS")

            # Wait for client in background
            import threading
            def wait_client():
                event_pipe.wait_for_client()
            client_thread = threading.Thread(target=wait_client, daemon=True)
            client_thread.start()

        # Spawn viewer terminal
        from event_viewer import spawn_viewer
        if spawn_viewer():
            add_alert("[Startup] Event Viewer launched", "SUCCESS")
        else:
            add_alert("[Startup] Event Viewer launch failed (continuing...)", "WARNING")
    except Exception as e:
        add_alert(f"[Startup] Viewer error: {str(e)[:50]} (continuing...)", "WARNING")

    time.sleep(1)

    # ============================================
    # Step 3: Launch Super Menu
    # ============================================
    print("[Startup] Step 3: Starting Super Menu...")
    print("")

    from super_menu import super_menu
    super_menu()
