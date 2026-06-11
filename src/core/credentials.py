from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from core.constants import CONFIG_ROOT


DEFAULT_CONFIG_ROOT = Path(CONFIG_ROOT)
PASSWORD_FILE = "password.txt"
CREDENTIALS_FILE = "credentials.enc"


@dataclass(frozen=True)
class TradingCredentials:
    kis_app_key: str
    kis_app_secret: str
    kis_hts_id: str
    toss_client_id: str = ""
    toss_client_secret: str = ""


def generate_key_from_password(password: str) -> bytes:
    salt = b"Steven is human."
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def load_credentials(
    *,
    config_root: Path | str = DEFAULT_CONFIG_ROOT,
) -> TradingCredentials:
    root = Path(config_root)
    password = (root / PASSWORD_FILE).read_text(encoding="utf-8").strip()
    fernet = Fernet(generate_key_from_password(password))
    encrypted_data = (root / CREDENTIALS_FILE).read_bytes()
    fields = [field.strip() for field in fernet.decrypt(encrypted_data).decode().split(",")]

    if len(fields) == 3:
        return TradingCredentials(
            kis_app_key=fields[0],
            kis_app_secret=fields[1],
            kis_hts_id=fields[2],
        )

    if len(fields) == 5:
        return TradingCredentials(
            kis_app_key=fields[0],
            kis_app_secret=fields[1],
            kis_hts_id=fields[2],
            toss_client_id=fields[3],
            toss_client_secret=fields[4],
        )

    raise ValueError(
        "credentials.enc must contain either 3 KIS fields or 5 KIS/Toss fields"
    )


def get_secrets_from_password() -> tuple[str | None, str | None, str | None]:
    print("--- API Key loading ---")
    try:
        credentials = load_credentials()
    except Exception as exc:
        print(f"Error loading credentials: {exc}")
        return None, None, None

    return (
        credentials.kis_app_key,
        credentials.kis_app_secret,
        credentials.kis_hts_id,
    )
