import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from data.gsheet import parse_worksheet_data


class FakeWorksheet:
    def __init__(self, rows):
        self.rows = rows

    def get_all_values(self):
        return self.rows


def test_cash_only_gsheet_accounts_get_account_ids():
    worksheet = FakeWorksheet([
        ["ticker", "name", "qty", "avg_price", "investment", "account", "cur_price"],
        ["", "", "", "", "", "", ""],
        ["예수금", "예수금", "48824198", "", "", "CMA", ""],
        ["예수금", "예수금", "1028394", "", "", "CMA 보조", ""],
    ])

    parsed = parse_worksheet_data(worksheet, "KRW")

    assert parsed["accounts"] == {
        "CMA": {"name": "CMA"},
        "CMA 보조": {"name": "CMA 보조"},
    }
    assert parsed["cash_holdings"] == [
        {
            "account_name": "CMA",
            "account_key": "CMA",
            "amount": 48824198.0,
            "currency": "KRW",
        },
        {
            "account_name": "CMA 보조",
            "account_key": "CMA 보조",
            "amount": 1028394.0,
            "currency": "KRW",
        },
    ]


def test_gsheet_parser_ignores_sheet_current_price_column():
    worksheet = FakeWorksheet([
        ["ticker", "name", "qty", "avg_price", "investment", "account", "cur_price"],
        ["", "", "", "", "", "", ""],
        ["005930", "Samsung Electronics", "1", "70000", "", "ISA", "999999"],
    ])

    parsed = parse_worksheet_data(worksheet, "KRW")

    assert parsed["holdings"] == [
        {
            "account_key": "ISA",
            "ticker": "005930",
            "name": "Samsung Electronics",
            "qty": 1.0,
            "avg_price": 70000.0,
        }
    ]
