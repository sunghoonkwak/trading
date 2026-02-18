# -*- coding: utf-8 -*-
"""
Market State Management Module (Advanced)

Tracks real-time stock prices with validation and thread-safe persistence.
"""
import os
import json
import threading
import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

# Module directory for data file
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
STOCK_DATA_FILE = os.path.join(os.path.dirname(MODULE_DIR), "stock_data.json")

class MarketStateManager:
    """Singleton manager for high-integrity market data."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(MarketStateManager, cls).__new__(cls)
                cls._instance._data = {}
                cls._instance._persistence_running = False
                cls._instance._first_data_received = False
                cls._instance._load_from_disk()
        return cls._instance

    @property
    def stock_data_state(self) -> Dict:
        """Exposed for legacy compatibility. Use get_ticker() for new code."""
        return self._data

    def update_ticker(self, ticker: str, update_dict: Dict[str, Any]):
        """Updates ticker data with validation."""
        if not ticker or not isinstance(update_dict, dict):
            return

        with self._lock:
            # 1. Initialize if new
            if ticker not in self._data:
                self._data[ticker] = {
                    'price': 0.0, 'ask': 0.0, 'bid': 0.0, 'change': 0.0,
                    'rate': 0.0, 'vol': 0, 'time': '000000'
                }

            # 2. Validate and Update
            target = self._data[ticker]
            for key, val in update_dict.items():
                if key in target:
                    # Basic numeric validation
                    if key in ['price', 'ask', 'bid', 'vol'] and (not isinstance(val, (int, float)) or val < 0):
                        continue
                    target[key] = val

            # 3. Handle Persistence Trigger
            if not self._first_data_received:
                self._first_data_received = True
                self._start_periodic_save()

    def get_ticker(self, ticker: str) -> Optional[Dict]:
        """Thread-safe access to a single ticker's data."""
        with self._lock:
            data = self._data.get(ticker)
            return data.copy() if data else None

    def get_price(self, ticker: str) -> float:
        """Helper to get current price directly."""
        data = self.get_ticker(ticker)
        return data.get('price', 0.0) if data else 0.0

    def get_all_tickers(self) -> List[str]:
        """Returns a list of all tracked tickers."""
        with self._lock:
            return list(self._data.keys())

    def _load_from_disk(self) -> bool:
        """Internal load logic with expiry check."""
        try:
            if os.path.exists(STOCK_DATA_FILE):
                with open(STOCK_DATA_FILE, 'r', encoding='utf-8') as f:
                    content = json.load(f)

                saved_state = content.get('stock_data', {})
                saved_time_str = content.get('updated_at', 'Unknown')

                if not saved_state or saved_time_str == 'Unknown':
                    return False

                saved_time = datetime.strptime(saved_time_str, '%Y-%m-%d %H:%M:%S')
                # Ignore if older than 5 minutes
                if (datetime.now() - saved_time).total_seconds() / 60.0 < 5:
                    self._data.update(saved_state)
                    logging.info(f"[MarketState] Loaded {len(saved_state)} stocks from cache")
                    return True
        except Exception as e:
            logging.warning(f"[MarketState] Initial load failed: {e}")
        return False

    def save_to_disk(self) -> bool:
        """Explicitly save current state to disk."""
        try:
            with self._lock:
                data_copy = {k: v.copy() for k, v in self._data.items()}

            # Filter corrupted keys
            for ticker in list(data_copy.keys()):
                if not ticker or len(ticker) > 12 or any(ord(c) < 32 for c in ticker):
                    del data_copy[ticker]

            payload = {
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'stock_data': data_copy
            }
            with open(STOCK_DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            logging.info(f"[MarketState] Successfully saved {len(data_copy)} stocks to disk")
            return True
        except Exception as e:
            logging.error(f"[MarketState] Disk save failed: {e}")
            return False

    def _start_periodic_save(self):
        """Launches background persistence thread."""
        from core.constants import MARKET_STATE_SAVE_INTERVAL
        if self._persistence_running:
            return
        self._persistence_running = True

        def worker():
            while self._persistence_running:
                time.sleep(MARKET_STATE_SAVE_INTERVAL)
                if self._persistence_running:
                    self.save_to_disk()

        t = threading.Thread(target=worker, daemon=True, name="MarketStateSaver")
        t.start()

    def stop_persistence(self):
        """Stops background thread and performs final save."""
        self._persistence_running = False
        self.save_to_disk()

# =============================================================================
# Global Convenience Interface (Singelton access)
# =============================================================================
_manager = MarketStateManager()

def get_market_manager() -> MarketStateManager:
    return _manager

# Module-level alias so code like `import state.market_state as m; m.stock_data_state[...]`
# works without going through the class instance explicitly.
stock_data_state: Dict = _manager._data

def notify_data_received():
    """Legacy hook – persistence is handled by MarketStateManager internally."""
    pass

# Functional aliases for easier migration
def update_ticker(ticker: str, data: Dict): _manager.update_ticker(ticker, data)
def get_ticker_data(ticker: str) -> Optional[Dict]: return _manager.get_ticker(ticker)
def get_all_market_data() -> Dict:
    with _manager._lock: return _manager._data.copy()
