import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


def test_data_service_toss_scope_filters_toss_account(monkeypatch):
    from data import data_service

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

    scoped = data_service._apply_scope_filter(data, "toss")

    assert {holding["ticker"] for holding in scoped["holdings"]} == {"AAPL"}
    assert set(scoped["merged_data"]) == {"AAPL", "USD cash"}
    assert scoped["merged_data"]["USD cash"]["qty"] == 20


def test_data_service_passes_scope_to_portfolio_worker(monkeypatch):
    from data import data_service

    captured = {}

    class Response:
        success = False
        error = "stop after request"

    monkeypatch.setattr(data_service, "is_kis_ready", lambda: True)
    monkeypatch.setattr(data_service, "add_alert", lambda message, level: None)
    monkeypatch.setattr(
        data_service,
        "request_portfolio",
        lambda force_refresh=False, scope="all": captured.update(
            {"force_refresh": force_refresh, "scope": scope}
        ) or "request-1",
    )
    monkeypatch.setattr(
        data_service,
        "wait_for_response",
        lambda request_id, timeout=60.0: Response(),
    )

    result = data_service.get_portfolio_data(force_refresh=True, scope="toss")

    assert result == {"error": "stop after request"}
    assert captured == {"force_refresh": True, "scope": "toss"}
