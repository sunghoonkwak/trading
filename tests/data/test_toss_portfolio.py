import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


def test_fetch_toss_portfolio_converts_api_payload(monkeypatch):
    from broker import toss_portfolio

    captured = {"buying_power": []}

    monkeypatch.setattr(
        "toss.auth.load_access_token",
        lambda: "access-token",
    )
    monkeypatch.setattr(
        "toss.get_holdings.get_holdings",
        lambda **kwargs: {
            "items": [
                {
                    "symbol": "005930",
                    "name": "삼성전자",
                    "marketCountry": "KR",
                    "currency": "KRW",
                    "quantity": "10",
                    "lastPrice": "72000",
                    "averagePurchasePrice": "65000",
                },
                {
                    "symbol": "AAPL",
                    "name": "Apple Inc.",
                    "marketCountry": "US",
                    "currency": "USD",
                    "quantity": "2.5",
                    "lastPrice": "178.5",
                    "averagePurchasePrice": "155.3",
                },
            ]
        },
    )

    def fake_buying_power(**kwargs):
        captured["buying_power"].append(kwargs)
        return {
            "currency": kwargs["currency"],
            "cashBuyingPower": "5000000" if kwargs["currency"] == "KRW" else "3500.5",
        }

    monkeypatch.setattr("toss.get_buying_power.get_buying_power", fake_buying_power)

    source, error = toss_portfolio.fetch_toss_portfolio()

    assert error is None
    assert source["accounts"] == {
        "토스": {"name": "토스"}
    }
    assert source["holdings"] == [
        {
            "account_key": "토스",
            "ticker": "005930",
            "name": "삼성전자",
            "qty": 10.0,
            "avg_price": 65000.0,
            "cur_price": 72000.0,
        },
        {
            "account_key": "토스",
            "ticker": "AAPL",
            "name": "Apple Inc.",
            "qty": 2.5,
            "avg_price": 155.3,
            "cur_price": 178.5,
        },
    ]
    assert source["asset_info"]["005930"]["market"] == "KR"
    assert source["asset_info"]["AAPL"]["currency"] == "USD"
    assert source["cash_holdings"] == [
        {
            "account_name": "토스",
            "account_key": "토스",
            "amount": 5000000.0,
            "currency": "KRW",
        },
        {
            "account_name": "토스",
            "account_key": "토스",
            "amount": 3500.5,
            "currency": "USD",
        },
    ]
    assert [call["currency"] for call in captured["buying_power"]] == ["KRW", "USD"]
