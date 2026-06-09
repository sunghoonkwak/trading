import sys
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def test_kis_constants_own_order_and_exchange_codes():
    from kis.constants import (
        EXCHANGE_CODE_MAP,
        ORDER_TYPE_US_LIMIT,
        ORDER_TYPE_US_LOC,
    )

    assert ORDER_TYPE_US_LIMIT == "00"
    assert ORDER_TYPE_US_LOC == "34"
    assert EXCHANGE_CODE_MAP["NAS"] == "NASD"


def test_strategy_constants_own_strategy_defaults():
    from strategy.constants import (
        DEFAULT_REBALANCE_THRESHOLD,
        DEFAULT_VA_THRESHOLD,
        MAX_BUY_PRICE_RATIO,
    )

    assert DEFAULT_VA_THRESHOLD == 0.15
    assert DEFAULT_REBALANCE_THRESHOLD == 0.05
    assert MAX_BUY_PRICE_RATIO == 1.25
