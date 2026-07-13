import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))


def test_data_service_toss_scope_filters_toss_account(monkeypatch):
    from application.portfolio_service import PortfolioService

    raw = {
        "metadata": {"exchange_rate": 1300.0},
        "asset_info": {
            "QQQM": {"currency": "USD"},
            "AAPL": {"currency": "USD"},
        },
        "accounts": [
            {"id": "acc_01", "name": "한국투자증권"},
            {"id": "acc_02", "name": "토스"},
        ],
        "holdings": [
            {
                "account_id": "acc_01",
                "ticker": "QQQM",
                "name": "QQQM",
                "qty": 1,
                "avg_price": 100,
                "cur_price": 100,
            },
            {
                "account_id": "acc_02",
                "ticker": "AAPL",
                "name": "Apple",
                "qty": 2,
                "avg_price": 150,
                "cur_price": 160,
            },
        ],
        "cash_holdings": [
            {
                "account_id": "acc_01",
                "account_name": "한국투자증권",
                "amount": 10,
                "currency": "USD",
            },
            {
                "account_id": "acc_02",
                "account_name": "토스",
                "amount": 20,
                "currency": "USD",
            },
        ],
    }
    data = {
        "raw": raw,
        "merged_data": {},
        "total_value_usd": 0,
        "stats": {},
        "accounts": raw["accounts"],
        "holdings": raw["holdings"],
        "metadata": raw["metadata"],
    }

    scoped = PortfolioService.apply_scope_filter(data, "toss")

    assert {holding["ticker"] for holding in scoped["holdings"]} == {"AAPL"}
    assert set(scoped["merged_data"]) == {"AAPL", "USD cash"}
    assert scoped["merged_data"]["USD cash"]["qty"] == 20


def test_portfolio_composition_passes_scope_to_sources_without_worker_dispatch():
    from infrastructure.portfolio import composition

    captured = {}

    class Source:
        def fetch(self, *, scope):
            captured["scope"] = scope
            raise RuntimeError("stop after request")

    service = composition.build_portfolio_service(
        composition.PortfolioServiceDependencies(
            is_kis_ready=lambda: True,
            portfolio_source=Source(),
            save_portfolio=lambda _value: None,
            load_weights=lambda: {},
            calculate_targets=lambda *_args: ({}, None, None),
            fear_and_greed=lambda: 50,
            publish_alert=lambda _message, _level: None,
        )
    )

    try:
        service.get_portfolio_data(force_refresh=True, scope="toss")
    except RuntimeError as exc:
        assert str(exc) == "stop after request"
    else:
        raise AssertionError("source adapter must be called")

    assert captured == {"scope": "toss"}
