import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from application.portfolio_service import PortfolioService


class _Response:
    success = True
    result = {
        "metadata": {"exchange_rate": 1_300.0},
        "asset_info": {"AAPL": {"currency": "USD"}},
        "accounts": [{"id": "toss-1", "name": "토스"}],
        "holdings": [
            {
                "account_id": "toss-1",
                "ticker": "AAPL",
                "name": "Apple",
                "qty": 2,
                "avg_price": 100.0,
                "cur_price": 120.0,
            }
        ],
        "cash_holdings": [],
    }


def test_portfolio_service_uses_injected_ports_and_preserves_scope_result():
    calls = []
    service = PortfolioService(
        is_kis_ready=lambda: True,
        request_portfolio=lambda **kwargs: calls.append(kwargs) or "request-1",
        wait_for_response=lambda *_args, **_kwargs: _Response(),
        save_portfolio=lambda value: calls.append({"saved": value}),
        load_weights=lambda: {},
        calculate_targets=lambda *_args: ({}, None, None),
        fear_and_greed=lambda: 50,
        publish_alert=lambda message, level: calls.append({"alert": (message, level)}),
    )

    result = service.get_portfolio_data(force_refresh=True, scope="toss")

    assert {"force_refresh": True, "scope": "toss"} in calls
    assert result["holdings"] == _Response.result["holdings"]
    assert result["total_value_usd"] == 240.0
    assert result["targets"] == {}


def test_portfolio_service_fails_closed_before_request_when_kis_is_not_ready():
    service = PortfolioService(
        is_kis_ready=lambda: False,
        request_portfolio=lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not request")),
        wait_for_response=lambda *_args, **_kwargs: None,
        save_portfolio=lambda _value: None,
        load_weights=lambda: {},
        calculate_targets=lambda *_args: ({}, None, None),
        fear_and_greed=lambda: 50,
        publish_alert=lambda *_args: None,
    )

    assert service.get_portfolio_data() == {"error": "KIS Thread not ready"}
