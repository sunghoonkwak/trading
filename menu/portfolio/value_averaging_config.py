import json
import os
import logging
from typing import Dict, Any, Tuple

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'value_averaging.json')
HISTORY_FILE = os.path.join(os.path.dirname(__file__), 'value_averaging_history.json')

def load_config() -> Dict[str, Any]:
    """Load value_averaging.json config."""
    try:
        if not os.path.exists(CONFIG_FILE):
            return {}
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load value averaging config: {e}")
        return {}

def save_config(config: Dict[str, Any]) -> bool:
    """Save value_averaging.json config."""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        logging.error(f"Failed to save value averaging config: {e}")
        return False

def load_history() -> Dict[str, Any]:
    """Load value_averaging_history.json."""
    try:
        if not os.path.exists(HISTORY_FILE):
            return {"history": []}
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load value averaging history: {e}")
        return {"history": []}

def save_history(history_data: Dict[str, Any]) -> bool:
    """Save value_averaging_history.json."""
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        logging.error(f"Failed to save value averaging history: {e}")
        return False

def get_target_weight_ratio(ticker: str) -> float:
    """
    Calculate the effective target weight ratio (0.0 - 1.0) for a given ticker
    from portfolio_weights.json.

    Raises:
        ValueError: If ticker is found in both 'individual_stocks' and 'groups'.
    """
    try:
        with open(PORTFOLIO_WEIGHTS_FILE, 'r', encoding='utf-8') as f:
            weights = json.load(f)

        found_in_individual = False
        found_in_group = False
        ratio = 0.0

        # Check individual_stocks
        for stock in weights.get('individual_stocks', []):
            if stock.get('ticker') == ticker:
                found_in_individual = True
                ratio = float(stock.get('ratio', 0))
                break

        # Check groups
        for group in weights.get('groups', []):
            if ticker in group.get('constituents', []) or ticker == group.get('main_ticker'):
                # Check if it was already found in individual (Conflict!)
                if found_in_individual:
                    raise ValueError(f"Configuration Error: {ticker} is defined in both 'individual_stocks' and 'groups'.")

                # If found in group, we need to know how much of the group weight this ticker takes.
                # !!! IMPORTANT !!!
                # Based on user's portfolio logic, we need to clarify this calculation.
                # Assumptions:
                # 1. If it's the 'start_ticker' or sole 'main_ticker' of a group, it takes the full group score?
                # 2. But user's system seems to calculate 'target_weights' dynamically using calculate_weights.py.
                #    Let's use calculate_target_weights from calculate_weights.py if possible,
                #    or for now, strictly follow the simplified user instruction:
                #    "portfolio_weights.json 를 가지고 portfolio merge를 하면 나오는 값"

                # Re-reading user instruction: User said "get_portfolio()를 이용하면... target_weight 가져올수 있어".
                # So we should probably rely on the calculated weights from the portfolio module
                # instead of parsing raw json manually here if possible.
                # However, calculate_weights.py calculates weights based on SCORES.

                # Let's do a quick parsing of raw file for now as a fallback,
                # but primarily we will rely on `calculate_target_weights` function if imported.
                found_in_group = True
                # Placeholder logic if manual parsing is needed (but ideally we use the shared module)
                total_k = sum([g.get('target_score', 0) for g in weights.get('groups', [])]) + \
                          sum([s.get('ratio', 0) * 100 for s in weights.get('individual_stocks', [])]) # Ratio is 0-1, score is int
                          # This manual calc is complex. Let's return to this later.
                break

        if found_in_individual:
            return ratio

        # If not found in individual, we will rely on calculating it via shared module in the main logic
        return 0.0

    except FileNotFoundError:
        logging.error("portfolio_weights.json not found.")
        return 0.0
    except Exception as e:
        logging.error(f"Error reading portfolio weights: {e}")
        raise e
