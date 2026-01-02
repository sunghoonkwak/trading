"""
This is the main entry point of the KIS Trading System.
It initializes authentication, WebSocket connections, and the interactive menu.
"""
import logging
import os
import re
from datetime import datetime
import pandas as pd
import msvcrt
import threading
import sys
import shutil
import subprocess

# Force-disable any global requests-cache to prevent SQLite multi-thread errors
try:
    import requests_cache
    if requests_cache.is_installed():
        requests_cache.uninstall_cache()
except ImportError:
    pass

# Import refactored modules
import trading_config
from trading_config import strip_market_prefix
import trading_state
import display
from display import render_ui, show_in_result_area, safe_write, get_fixed_width_name, clear_result_area, input_at, prepare_exit, update_order_state, add_alert
from kis import event_pipe

from menu.menu import menu

# Specific KIS imports
from kis.kis_api.domestic_stock.asking_price_total.asking_price_total import asking_price_total
from kis.kis_api.domestic_stock.ccnl_total.ccnl_total import ccnl_total
from kis.kis_api.overseas_stock.asking_price.asking_price import asking_price
from menu.handle_manage_orders import sync_open_orders, request_sync
from kis.kis_api.overseas_stock.ccnl_notice.ccnl_notice import ccnl_notice
from kis.kis_api.overseas_stock.delayed_ccnl.delayed_ccnl import delayed_ccnl

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

def write_cleared(text, end="\n"):
    safe_write(f"{display.CLEAR_LINE}{text}{end}")

_viewer_process = None

def spawn_viewer():
    """Spawn the Event viewer in Windows Terminal."""
    global _viewer_process
    viewer_path = os.path.join(base_dir, "event_viewer.py")
    try:
        # Use Windows Terminal (wt) - opens in new tab with size 140x35
        _viewer_process = subprocess.Popen(
            ["wt", "-w", "0", "--size", "130,35", "nt", "--title", "Event Viewer",
             "python", viewer_path],
            cwd=base_dir
        )
        logging.info("[System] Viewer terminal spawned")
        return True
    except Exception as e:
        logging.error(f"[System] Failed to spawn viewer: {e}")
        return False

def close_viewer():
    """Close the viewer terminal if running."""
    global _viewer_process
    if _viewer_process is not None:
        try:
            _viewer_process.terminate()
            _viewer_process = None
            logging.info("[System] Viewer terminal closed")
        except:
            pass




if __name__ == "__main__":
    print("=== KIS Real-time Trading System ===")

    # Import and run super_menu (handles thread initialization)
    from super_menu import super_menu
    super_menu()

