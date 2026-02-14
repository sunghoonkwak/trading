# -*- coding: utf-8 -*-
"""
Market State Management Module

Tracks real-time stock prices and handles persistence to disk.
"""
import os
import json
import threading
import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
STOCK_DATA_FILE = os.path.join(os.path.dirname(MODULE_DIR), "stock_data.json")

class MarketStateManager:
    """Singleton manager for real-time market data."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(MarketStateManager, cls).__new__(cls)
                cls._instance._data = {}
                cls._instance._persistence_running = False
                cls._instance._first_data_received = False
                cls._instance.load_from_disk()
        return cls._instance

    @property
    def stock_data_state(self) -> Dict:
        """Expose raw data for legacy code compatibility."""
        return self._data

    def update_ticker(self, ticker: str, update_dict: Dict[str, Any]):
        with self._lock:
            if ticker not in self._data:
                self._data[ticker] = {
                    'price': 0, 'ask': 0, 'bid': 0, 'change': 0,
                    'rate': 0.0, 'vol': 0, 'time': '000000'
                }
            self._data[ticker].update(update_dict)
            
            if not self._first_data_received:
                self._first_data_received = True
                self._start_periodic_save()

    def get_ticker(self, ticker: str) -> Optional[Dict]:
        with self._lock:
            return self._data.get(ticker)

    def load_from_disk(self) -> bool:
        try:
            if os.path.exists(STOCK_DATA_FILE):
                with open(STOCK_DATA_FILE, 'r', encoding='utf-8') as f:
                    content = json.load(f)
                saved_state = content.get('stock_data', {})
                saved_time_str = content.get('updated_at', 'Unknown')
                if not saved_state or saved_time_str == 'Unknown': return False
                saved_time = datetime.strptime(saved_time_str, '%Y-%m-%d %H:%M:%S')
                if (datetime.now() - saved_time).total_seconds() / 60.0 < 5:
                    self._data.update(saved_state)
                    logging.info(f"[MarketState] Loaded {len(saved_state)} stocks from cache")
                    return True
        except Exception as e: logging.warning(f"[MarketState] Load failed: {e}")
        return False

    def save_to_disk(self) -> bool:
        try:
            with self._lock: data_copy = self._data.copy()
            for code in list(data_copy.keys()):
                if len(code) == 0 or any(ord(c) < 32 for c in code): del data_copy[code]
            payload = {'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'stock_data': data_copy}
            with open(STOCK_DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            logging.info(f"[MarketState] Saved {len(data_copy)} stocks")
            return True
        except Exception as e: logging.warning(f"[MarketState] Save failed: {e}"); return False

    def _start_periodic_save(self):
        if self._persistence_running: return
        self._persistence_running = True
        def worker():
            while self._persistence_running:
                time.sleep(60)
                if self._persistence_running: self.save_to_disk()
        threading.Thread(target=worker, daemon=True, name="MarketStateSaver").start()

    def stop_persistence(self):
        self._persistence_running = False
        self.save_to_disk()

# =============================================================================
# Global Convenience Interface (To replace trading_state.py)
# =============================================================================
_m_manager = MarketStateManager()
stock_data_state = _m_manager.stock_data_state

def load_stock_data(): return _m_manager.load_from_disk()
def save_stock_data(): return _m_manager.save_to_disk()
def notify_data_received(): _m_manager._first_data_received = True; _m_manager._start_periodic_save()
def stop_periodic_save(): _m_manager.stop_persistence()
