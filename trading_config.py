import os
import json

# Load Stock Configuration from JSON
STOCK_CONFIG = {}
try:
    _json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stock_configuration.json")
    if os.path.exists(_json_path):
        with open(_json_path, "r", encoding="utf-8") as f:
            STOCK_CONFIG = json.load(f)
except Exception as e:
    pass
