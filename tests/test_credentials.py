import sys
import unittest
from pathlib import Path

from cryptography.fernet import Fernet


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


class CredentialsTest(unittest.TestCase):
    def test_load_credentials_reads_kis_and_toss_values(self):
        from core.credentials import (
            generate_key_from_password,
            load_credentials,
        )

        config_root = ROOT / "tests" / ".tmp-credentials"
        self.addCleanup(lambda: self._remove_tree(config_root))
        config_root.mkdir(exist_ok=True)
        (config_root / "password.txt").write_text("test-password\n", encoding="utf-8")

        fernet = Fernet(generate_key_from_password("test-password"))
        encrypted = fernet.encrypt(
            b"kis-key,kis-secret,hts-id,toss-client-id,toss-client-secret"
        )
        (config_root / "credentials.enc").write_bytes(encrypted)

        credentials = load_credentials(config_root=config_root)

        self.assertEqual(credentials.kis_app_key, "kis-key")
        self.assertEqual(credentials.kis_app_secret, "kis-secret")
        self.assertEqual(credentials.kis_hts_id, "hts-id")
        self.assertEqual(credentials.toss_client_id, "toss-client-id")
        self.assertEqual(credentials.toss_client_secret, "toss-client-secret")

    def test_legacy_kis_credentials_keep_toss_values_empty(self):
        from core.credentials import (
            generate_key_from_password,
            load_credentials,
        )

        config_root = ROOT / "tests" / ".tmp-legacy-credentials"
        self.addCleanup(lambda: self._remove_tree(config_root))
        config_root.mkdir(exist_ok=True)
        (config_root / "password.txt").write_text("test-password\n", encoding="utf-8")

        fernet = Fernet(generate_key_from_password("test-password"))
        (config_root / "credentials.enc").write_bytes(
            fernet.encrypt(b"kis-key,kis-secret,hts-id")
        )

        credentials = load_credentials(config_root=config_root)

        self.assertEqual(credentials.kis_app_key, "kis-key")
        self.assertEqual(credentials.kis_app_secret, "kis-secret")
        self.assertEqual(credentials.kis_hts_id, "hts-id")
        self.assertEqual(credentials.toss_client_id, "")
        self.assertEqual(credentials.toss_client_secret, "")

    def _remove_tree(self, path):
        if not path.exists():
            return
        for child in path.iterdir():
            child.unlink()
        path.rmdir()


if __name__ == "__main__":
    unittest.main()
