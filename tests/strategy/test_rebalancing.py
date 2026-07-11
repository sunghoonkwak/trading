import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from strategy import rebalancing


def test_rebalancing_skips_orders_when_an_asset_has_no_price():
    orders, info = rebalancing.calculate_orders(
        config={
            "seed": 1_000,
            "assets": [
                {"ticker": "TQQQ", "target_weight": 0.5},
                {"ticker": "SCHD", "target_weight": 0.5},
            ],
        },
        portfolio={
            "TQQQ": {"qty": 10, "cur_price": 100.0},
            "SCHD": {"qty": 0, "cur_price": 0.0},
        },
        current_prices={"TQQQ": 100.0, "SCHD": 0.0},
        orderable_usd=1_000.0,
    )

    assert orders == []
    assert set(info["asset_status"]) == {"TQQQ"}
