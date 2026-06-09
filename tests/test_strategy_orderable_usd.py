import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from strategy import execution_service, rebalancing
from strategy.base import OrderSide


def test_get_orderable_usd_delegates_to_broker(monkeypatch):
    calls = {}

    monkeypatch.setattr(
        execution_service.kis_broker,
        "get_orderable_usd",
        lambda symbol, price: calls.setdefault((symbol, price), 3023.49),
    )

    amount = execution_service.get_orderable_usd("SOXL", 25.40)

    assert amount == 3023.49
    assert calls == {("SOXL", 25.40): 3023.49}


def test_rebalancing_uses_orderable_usd_instead_of_portfolio_cash():
    config = {
        "seed": 2000,
        "assets": [
            {"ticker": "TQQQ", "target_weight": 0.5},
            {"ticker": "SCHD", "target_weight": 0.5},
        ],
        "rebalance_threshold": 0.05,
    }
    portfolio = {
        "TQQQ": {"qty": 10, "cur_price": 100.0, "avg_price": 100.0},
        "SCHD": {"qty": 0, "cur_price": 100.0, "avg_price": 0.0},
        "USD cash": {"qty": 0.0},
    }

    orders, info = rebalancing.calculate_orders(
        config=config,
        portfolio=portfolio,
        current_prices={"TQQQ": 100.0, "SCHD": 100.0},
        orderable_usd=1000.0,
    )

    assert any(order.symbol == "SCHD" for order in orders)
    assert info["orderable_usd"] == 1000.0


def test_run_raoeo_does_not_automatically_query_or_sell_cash_ticker(monkeypatch):
    config = {
        "cash_ticker": "BIL",
        "raoeo": {
            "enabled": True,
            "targets": {
                "TQQQ": {
                    "enabled": True,
                    "seed": 1000,
                    "duration": 1,
                    "phase": [{
                        "name": "initial",
                        "threshold": 1.0,
                        "buy": [{"type": "normal", "ratio": 1.0}],
                        "sell": [],
                    }],
                },
            },
        },
    }
    monkeypatch.setattr(
        execution_service,
        "_get_market_status",
        lambda today: {"is_market_open": True, "is_holiday": False, "message": ""},
    )
    monkeypatch.setattr(execution_service, "_load_history", lambda: [])
    monkeypatch.setattr(
        execution_service,
        "load_json",
        lambda file_type, default=None: config,
    )
    monkeypatch.setattr(
        execution_service,
        "get_market_data",
        lambda force_refresh=False: (
            {"BIL": {"qty": 100, "cur_price": 100.0}},
            {"TQQQ": 100.0, "BIL": 100.0},
        ),
    )
    monkeypatch.setattr(
        execution_service,
        "get_orderable_usd",
        lambda symbol, price: (_ for _ in ()).throw(
            AssertionError("automatic RAOEO execution must not fund cash")
        ),
    )

    report = execution_service.run_raoeo_strategy(execute=False)

    assert not any(
        order.symbol == "BIL" and order.side == OrderSide.SELL
        for order in report["orders"]
    )


def test_run_rebalancing_passes_api_orderable_usd_to_calculation(monkeypatch):
    config = {
        "raoeo": {"targets": {}},
        "rebalancing": {
            "enabled": True,
            "seed": 1000,
            "assets": [{"ticker": "TQQQ", "target_weight": 1.0}],
        },
    }
    received = {}
    monkeypatch.setattr(
        execution_service,
        "_get_market_status",
        lambda today: {"is_market_open": True, "is_holiday": False, "message": ""},
    )
    monkeypatch.setattr(execution_service, "_load_history", lambda: [])
    monkeypatch.setattr(
        execution_service,
        "load_json",
        lambda file_type, default=None: config,
    )
    monkeypatch.setattr(
        execution_service,
        "get_market_data",
        lambda force_refresh=False: ({}, {"TQQQ": 100.0}),
    )
    monkeypatch.setattr(
        execution_service,
        "get_orderable_usd",
        lambda symbol, price: 3023.49,
    )

    def fake_calculate_orders(**kwargs):
        received.update(kwargs)
        return [], {}

    monkeypatch.setattr(
        execution_service.rebalancing,
        "calculate_orders",
        fake_calculate_orders,
    )

    execution_service.run_rebalancing_strategy(execute=False)

    assert received["orderable_usd"] == 3023.49
