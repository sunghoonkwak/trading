import sys
from pathlib import Path
import importlib.util

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))


def _load_gsheet_module():
    spec = importlib.util.spec_from_file_location(
        "gsheet_under_test",
        SRC_DIR / "kis" / "gsheet.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


parse_worksheet_data = _load_gsheet_module().parse_worksheet_data


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
        ["예수금", "예수금", "1028394", "", "", "CMA 인선", ""],
    ])

    parsed = parse_worksheet_data(worksheet, "KRW")

    assert parsed["accounts"] == {
        "CMA_owner_01": {"name": "CMA", "owner_id": "owner_01"},
        "CMA 인선_owner_02": {"name": "CMA 인선", "owner_id": "owner_02"},
    }
    assert parsed["cash_holdings"] == [
        {
            "account_name": "CMA",
            "account_key": "CMA_owner_01",
            "amount": 48824198.0,
            "currency": "KRW",
        },
        {
            "account_name": "CMA 인선",
            "account_key": "CMA 인선_owner_02",
            "amount": 1028394.0,
            "currency": "KRW",
        },
    ]
