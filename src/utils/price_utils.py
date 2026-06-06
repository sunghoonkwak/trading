# -*- coding: utf-8 -*-
"""Price resolution helpers shared across services."""
from typing import Dict


def resolve_current_price(
    ticker: str,
    holding: Dict,
    current_prices: Dict[str, float],
) -> float:
    """Use explicit current price first, then fall back to holding cur_price."""
    cur_price = current_prices.get(ticker, 0.0)
    if cur_price <= 0:
        cur_price = float(holding.get("cur_price", 0.0))
    return cur_price
