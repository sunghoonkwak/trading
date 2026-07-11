"""Price resolution used only by domain strategy calculations."""

from typing import Dict


def resolve_current_price(
    ticker: str,
    holding: Dict,
    current_prices: Dict[str, float],
) -> float:
    """Use an explicit current price, then the holding's current price."""
    cur_price = current_prices.get(ticker, 0.0)
    if cur_price <= 0:
        cur_price = float(holding.get("cur_price", 0.0))
    return cur_price
