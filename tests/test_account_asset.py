import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


class AccountAssetTest(unittest.TestCase):
    def test_get_accounts_sends_bearer_token(self):
        from toss.get_accounts import get_accounts

        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return json.dumps(
                    {
                        "result": [
                            {
                                "accountNo": "12345678901",
                                "accountSeq": 1,
                                "accountType": "BROKERAGE",
                            }
                        ]
                    }
                ).encode("utf-8")

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["timeout"] = timeout
            return FakeResponse()

        accounts = get_accounts(
            access_token="access-token",
            base_url="https://example.test",
            urlopen=fake_urlopen,
        )

        self.assertEqual(captured["url"], "https://example.test/api/v1/accounts")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer access-token")
        self.assertEqual(captured["timeout"], 10.0)
        self.assertEqual(accounts[0]["accountSeq"], 1)
        self.assertEqual(accounts[0]["accountType"], "BROKERAGE")

    def test_get_holdings_sends_account_header_and_optional_symbol(self):
        from toss.get_holdings import get_holdings

        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return json.dumps(
                    {
                        "result": {
                            "items": [
                                {
                                    "symbol": "005930",
                                    "name": "삼성전자",
                                    "quantity": "10",
                                }
                            ]
                        }
                    }
                ).encode("utf-8")

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["timeout"] = timeout
            return FakeResponse()

        holdings = get_holdings(
            account_seq=1,
            access_token="access-token",
            symbol="005930",
            base_url="https://example.test",
            urlopen=fake_urlopen,
        )

        self.assertEqual(captured["url"], "https://example.test/api/v1/holdings?symbol=005930")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer access-token")
        self.assertEqual(captured["headers"]["X-tossinvest-account"], "1")
        self.assertEqual(captured["timeout"], 10.0)
        self.assertEqual(holdings["items"][0]["symbol"], "005930")

    def test_account_and_holdings_scripts_can_run_directly(self):
        for script in ("src/toss/get_accounts.py", "src/toss/get_holdings.py"):
            result = subprocess.run(
                [sys.executable, script, "--help"],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
