# -*- coding: utf-8 -*-
"""
Trading State Module

This module manages the runtime state of stock data received from WebSocket.
It also handles persistence to/from stock_data.json for faster program restarts.
"""
import os
import json
import threading
import time
from datetime import datetime

# Module directory for data file
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
STOCK_DATA_FILE = os.path.join(MODULE_DIR, "stock_data.json")

# Main stock data state dictionary
# Key: ticker symbol (e.g., "SOXL" or "DNASSOXL")
# Value: dict with price, ask, bid, change, rate, vol, time
stock_data_state = {}

# State for persistence
_first_data_received = False
_save_thread = None
_save_thread_running = False


def load_stock_data():
    """
    Load stock data from stock_data.json at program startup.
    Ignores data if it is older than 5 minutes.
    Returns True if data was loaded successfully.
    """
    global stock_data_state

    try:
        if os.path.exists(STOCK_DATA_FILE):
            with open(STOCK_DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            saved_state = data.get('stock_data', {})
            saved_time_str = data.get('updated_at', 'Unknown')

            import logging
            if not saved_state or saved_time_str == 'Unknown':
                return False

            # Check if the cached data is fresh (within 5 minutes)
            try:
                saved_time = datetime.strptime(saved_time_str, '%Y-%m-%d %H:%M:%S')
                time_diff = (datetime.now() - saved_time).total_seconds() / 60.0

                if time_diff > 5:
                    logging.info(f"[TradingState] Cached data is stale ({time_diff:.1f}m old). Skipping load.")
                    return False

                stock_data_state.update(saved_state)
                logging.info(f"[TradingState] Loaded {len(saved_state)} stocks from cache (saved {time_diff:.1f}m ago)")
                return True
            except Exception as te:
                logging.warning(f"[TradingState] Failed to parse saved time: {te}")
                return False

    except Exception as e:
        import logging
        logging.warning(f"[TradingState] Failed to load stock data: {e}")

    return False


def save_stock_data():
    """
    Save current stock_data_state to stock_data.json.
    """
    import logging
    try:
        # DEBUG: Check for corrupted codes before saving
        corrupted = []
        for code in stock_data_state.keys():
            # Domestic stocks: 6 digits, Overseas: alphanumeric with prefix
            if len(code) == 6:
                if not code.isdigit():
                    corrupted.append(code)
            elif len(code) > 12 or len(code) == 0:
                corrupted.append(code)
            # Check for control characters
            elif any(ord(c) < 32 for c in code):
                corrupted.append(code)

        if corrupted:
            logging.warning(
                f"[DEBUG-SAVE] Corrupted codes found before save! "
                f"count={len(corrupted)}, samples={[repr(c) for c in corrupted[:5]]}"
            )

        data = {
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'stock_data': stock_data_state.copy()
        }

        with open(STOCK_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logging.info(f"[TradingState] Saved {len(stock_data_state)} stocks")
        return True
    except Exception as e:
        logging.warning(f"[TradingState] Failed to save stock data: {e}")
        return False


def _periodic_save_worker():
    """
    Background worker that saves stock data every 60 seconds.
    """
    global _save_thread_running

    while _save_thread_running:
        time.sleep(60)  # Wait 60 seconds
        if _save_thread_running and stock_data_state:
            save_stock_data()


def notify_data_received():
    """
    Call this when first market data is received from WebSocket.
    Starts the periodic save thread.
    """
    global _first_data_received, _save_thread, _save_thread_running

    if _first_data_received:
        return  # Already started

    _first_data_received = True
    _save_thread_running = True

    # Start background save thread
    _save_thread = threading.Thread(target=_periodic_save_worker, daemon=True)
    _save_thread.start()


def stop_periodic_save():
    """
    Stop the periodic save thread (call on program exit).
    Also performs a final save.
    """
    global _save_thread_running

    _save_thread_running = False

    # Final save
    if stock_data_state:
        save_stock_data()
        import logging
        logging.info("[TradingState] Final save completed")


# Load cached data on module import
load_stock_data()
