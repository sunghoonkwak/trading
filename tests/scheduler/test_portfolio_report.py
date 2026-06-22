import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


def test_comparison_stats_uses_configured_exchange_rate_fallback(tmp_path, monkeypatch):
    from scheduler import scheduler_portfolio

    monkeypatch.setattr(
        scheduler_portfolio,
        "DEFAULT_USD_KRW_EXCHANGE_RATE",
        1000,
    )

    past_file = tmp_path / "portfolio_20260101.json"
    past_file.write_text(
        json.dumps(
            {
                "holdings": [
                    {"ticker": "AAPL", "qty": 1, "cur_price": 1},
                ],
                "cash_holdings": [],
            }
        ),
        encoding="utf-8",
    )

    current_data = {
        "holdings": [
            {"ticker": "AAPL", "qty": 1, "cur_price": 10},
        ],
        "cash_holdings": [],
    }

    result = scheduler_portfolio.get_comparison_stats(
        current_data,
        [str(past_file)],
        str(tmp_path / "portfolio_20260102.json"),
    )

    assert "+9 k" in result
