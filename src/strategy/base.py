from dataclasses import dataclass
from enum import Enum
from typing import Optional


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class StrategyStatus(Enum):
    """Unified status values for all strategy execution results."""
    EXECUTED = "executed"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    HOLIDAY = "holiday"
    NON_MARKET_TIME = "non_market_time"
    DISABLED = "disabled"
    ERROR = "error"
    ALREADY_DONE = "already_done"

@dataclass
class StrategyOrder:
    symbol: str
    side: OrderSide
    quantity: int
    price: float = 0.0  # 0 for market price
    reason: str = ""
    order_type: str = "00"  # "00": market, "01": limit
    target_budget: Optional[float] = None

    def __str__(self):
        side_str = "BUY" if self.side == OrderSide.BUY else "SELL"
        price_str = f"{self.price:,.2f}" if self.price > 0 else "MARKET"
        return f"[{self.symbol}] {side_str} {self.quantity} ({price_str}) - {self.reason}"
