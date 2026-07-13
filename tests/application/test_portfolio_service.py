import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from application.portfolio_retrieval_service import PortfolioRetrievalService
from application.portfolio_service import PortfolioService


class _Response:
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


class _Source:
    def __init__(self, calls):
        self._calls = calls

    def fetch(self, *, scope):
        self._calls.append({"scope": scope})
        return _Response.result


def test_portfolio_service_uses_injected_ports_and_preserves_scope_result():
    calls = []
    service = PortfolioService(
        is_kis_ready=lambda: True,
        portfolio_source=_Source(calls),
        save_portfolio=lambda value: calls.append({"saved": value}),
        load_weights=lambda: {},
        calculate_targets=lambda *_args: ({}, None, None),
        fear_and_greed=lambda: 50,
        publish_alert=lambda message, level: calls.append({"alert": (message, level)}),
    )

    result = service.get_portfolio_data(force_refresh=True, scope="toss")

    assert {"scope": "toss"} in calls
    assert result["holdings"] == _Response.result["holdings"]
    assert result["total_value_usd"] == 240.0
    assert result["targets"] == {}


def test_portfolio_service_fails_closed_before_request_when_kis_is_not_ready():
    service = PortfolioService(
        is_kis_ready=lambda: False,
        portfolio_source=type(
            "Source",
            (),
            {"fetch": lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not request"))},
        )(),
        save_portfolio=lambda _value: None,
        load_weights=lambda: {},
        calculate_targets=lambda *_args: ({}, None, None),
        fear_and_greed=lambda: 50,
        publish_alert=lambda *_args: None,
    )

    assert service.get_portfolio_data() == {"error": "KIS Thread not ready"}


def test_portfolio_retrieval_service_owns_all_scope_source_policy():
    alerts = []
    service = PortfolioRetrievalService(
        fetch_kis=lambda: (
            {"accounts": {"kis": {"name": "한국투자증권"}}, "holdings": [], "asset_info": {}, "cash_holdings": []},
            {"exchange_rate": 1300.0, "error": None},
        ),
        fetch_toss=lambda: (
            {"accounts": {"toss": {"name": "토스"}}, "holdings": [], "asset_info": {}, "cash_holdings": []},
            None,
        ),
        get_cached_gsheet=lambda: ({"accounts": {}, "holdings": [], "asset_info": {}, "cash_holdings": []}, None),
        fetch_toss_exchange_rate=lambda: (None, None),
        fetch_toss_prices=lambda _tickers: {},
        publish_alert=lambda message, level: alerts.append((message, level)),
        publish_warning=lambda _message: None,
        toss_account_key="toss",
    )

    result = service.fetch(scope="all")

    assert [account["name"] for account in result["accounts"]] == ["한국투자증권", "토스"]
    assert result["metadata"]["exchange_rate"] == 1300.0
    assert alerts == [("[Data] Loading cached GSheet data...", "INFO")]
