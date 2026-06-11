from __future__ import annotations

import getpass
import sys
from pathlib import Path

from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from core.constants import CONFIG_ROOT
from core.credentials import CREDENTIALS_FILE, PASSWORD_FILE, generate_key_from_password


def main() -> None:
    print("--- Trading API Credential Setup (inputs are hidden) ---")

    user_password = getpass.getpass("1. Set a password for file encryption: ")
    kis_app_key = getpass.getpass("2. Enter your KIS APP KEY: ")
    kis_app_secret = getpass.getpass("3. Enter your KIS APP SECRET: ")
    kis_hts_id = getpass.getpass("4. Enter your KIS HTS ID: ")
    toss_client_id = getpass.getpass("5. Enter your TOSS CLIENT ID: ")
    toss_client_secret = getpass.getpass("6. Enter your TOSS CLIENT SECRET: ")

    config_root = Path(CONFIG_ROOT)
    config_root.mkdir(parents=True, exist_ok=True)

    key = generate_key_from_password(user_password)
    encrypted_data = Fernet(key).encrypt(
        ",".join(
            [
                kis_app_key,
                kis_app_secret,
                kis_hts_id,
                toss_client_id,
                toss_client_secret,
            ]
        ).encode("utf-8")
    )

    (config_root / PASSWORD_FILE).write_text(user_password + "\n", encoding="utf-8")
    (config_root / CREDENTIALS_FILE).write_bytes(encrypted_data)

    print("\n" + "=" * 60)
    print(f"[SUCCESS] Wrote {config_root / CREDENTIALS_FILE}")
    print(f"[SUCCESS] Wrote {config_root / PASSWORD_FILE}")
    print("KIS and Toss credentials are now managed from ~/KIS_config.")
    print("=" * 60)


if __name__ == "__main__":
    main()
