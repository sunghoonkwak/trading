import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


class AuthTest(unittest.TestCase):
    def test_load_config_reads_credentials_file(self):
        from toss.auth import load_config
        from core.credentials import generate_key_from_password
        from cryptography.fernet import Fernet

        config_root = ROOT / "tests" / ".tmp-toss-config"
        self.addCleanup(lambda: self._remove_tree(config_root))
        config_root.mkdir(exist_ok=True)
        (config_root / "password.txt").write_text("test-password\n", encoding="utf-8")
        fernet = Fernet(generate_key_from_password("test-password"))
        (config_root / "credentials.enc").write_bytes(
            fernet.encrypt(
                b"kis-key,kis-secret,hts-id,dummy-client-id,dummy-client-secret"
            )
        )

        config = load_config(config_root=config_root)

        self.assertEqual(config.client_id, "dummy-client-id")
        self.assertEqual(config.client_secret, "dummy-client-secret")
        self.assertEqual(config.base_url, "https://openapi.tossinvest.com")

    def test_issue_token_posts_form_urlencoded_request(self):
        from toss.auth import TossAuthConfig, issue_token

        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return json.dumps(
                    {
                        "access_token": "issued-access-token",
                        "token_type": "Bearer",
                        "expires_in": 86400,
                    }
                ).encode("utf-8")

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["data"] = request.data.decode("utf-8")
            captured["timeout"] = timeout
            return FakeResponse()

        token = issue_token(
            TossAuthConfig(
                client_id="client-id",
                client_secret="client-secret",
                base_url="https://example.test",
            ),
            urlopen=fake_urlopen,
        )

        self.assertEqual(captured["url"], "https://example.test/oauth2/token")
        self.assertEqual(
            captured["headers"]["Content-type"],
            "application/x-www-form-urlencoded",
        )
        self.assertEqual(
            captured["data"],
            "grant_type=client_credentials&client_id=client-id&client_secret=client-secret",
        )
        self.assertEqual(captured["timeout"], 10.0)
        self.assertEqual(token.access_token, "issued-access-token")
        self.assertEqual(token.token_type, "Bearer")
        self.assertEqual(token.expires_in, 86400)

    def test_save_token_uses_issued_time_filename_and_loads_latest(self):
        from toss.auth import TossToken, load_latest_token, save_token

        token_dir = ROOT / "tests" / ".tmp-token"
        self.addCleanup(lambda: self._remove_tree(token_dir))
        issued_at = datetime(2026, 6, 11, 12, 34, 56, tzinfo=timezone.utc)

        saved_path = save_token(
            TossToken(
                access_token="issued-access-token",
                token_type="Bearer",
                expires_in=86400,
            ),
            token_dir=token_dir,
            issued_at=issued_at,
        )

        self.assertEqual(saved_path.name, "TOSS20260611_123456.json")
        saved_payload = json.loads(saved_path.read_text(encoding="utf-8"))
        self.assertEqual(saved_payload["access_token"], "issued-access-token")
        self.assertEqual(saved_payload["token_type"], "Bearer")
        self.assertEqual(saved_payload["expires_in"], 86400)
        self.assertEqual(saved_payload["issued_at"], "2026-06-11T12:34:56+00:00")
        self.assertEqual(saved_payload["expires_at"], "2026-06-12T12:34:56+00:00")
        self.assertEqual(load_latest_token(token_dir), saved_payload)

    def test_ensure_daily_token_reuses_today_token(self):
        from toss.auth import TossAuthConfig, ensure_daily_token

        token_dir = ROOT / "tests" / ".tmp-daily-token"
        self.addCleanup(lambda: self._remove_tree(token_dir))
        token_dir.mkdir()
        existing = token_dir / "TOSS20260611_000001.json"
        existing.write_text('{"access_token": "today-token"}\n', encoding="utf-8")

        def fail_issue(_config):
            raise AssertionError("token should not be issued when today's token exists")

        token_path = ensure_daily_token(
            TossAuthConfig(client_id="client-id", client_secret="client-secret"),
            token_dir=token_dir,
            now=datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc),
            issue_token_func=fail_issue,
        )

        self.assertEqual(token_path, existing)

    def test_ensure_daily_token_issues_after_date_changes(self):
        from toss.auth import TossAuthConfig, TossToken, ensure_daily_token

        token_dir = ROOT / "tests" / ".tmp-next-day-token"
        self.addCleanup(lambda: self._remove_tree(token_dir))
        token_dir.mkdir()
        (token_dir / "TOSS20260611_235959.json").write_text(
            '{"access_token": "yesterday-token"}\n',
            encoding="utf-8",
        )

        calls = []

        def fake_issue(config):
            calls.append(config.client_id)
            return TossToken(
                access_token="new-token",
                token_type="Bearer",
                expires_in=86400,
            )

        token_path = ensure_daily_token(
            TossAuthConfig(client_id="client-id", client_secret="client-secret"),
            token_dir=token_dir,
            now=datetime(2026, 6, 12, 0, 1, tzinfo=timezone.utc),
            issue_token_func=fake_issue,
        )

        self.assertEqual(calls, ["client-id"])
        self.assertEqual(token_path.name, "TOSS20260612_000100.json")
        self.assertEqual(
            json.loads(token_path.read_text(encoding="utf-8"))["access_token"],
            "new-token",
        )

    def _remove_tree(self, path):
        if not path.exists():
            return
        for child in path.iterdir():
            child.unlink()
        path.rmdir()


if __name__ == "__main__":
    unittest.main()
