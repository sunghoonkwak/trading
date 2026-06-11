from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable
from urllib import error, parse, request

from core.constants import CONFIG_ROOT
from core.credentials import load_credentials


DEFAULT_BASE_URL = "https://openapi.tossinvest.com"
DEFAULT_TIMEOUT = 10.0
CONFIG_ROOT_PATH = Path(CONFIG_ROOT)
TOKEN_DIR = CONFIG_ROOT_PATH


@dataclass(frozen=True)
class TossAuthConfig:
    client_id: str
    client_secret: str
    base_url: str = DEFAULT_BASE_URL


@dataclass(frozen=True)
class TossToken:
    access_token: str
    token_type: str
    expires_in: int


def load_config(config_root: Path | str = CONFIG_ROOT_PATH) -> TossAuthConfig:
    credentials = load_credentials(config_root=Path(config_root))
    config = TossAuthConfig(
        client_id=credentials.toss_client_id,
        client_secret=credentials.toss_client_secret,
    )

    missing = [
        name
        for name, value in (
            ("TOSS_CLIENT_ID", config.client_id),
            ("TOSS_CLIENT_SECRET", config.client_secret),
        )
        if not value or value.startswith("your-")
    ]
    if missing:
        raise ValueError(f"Missing Toss API credential(s): {', '.join(missing)}")

    return config


def issue_token(
    config: TossAuthConfig,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    urlopen: Callable[..., object] = request.urlopen,
) -> TossToken:
    token_url = f"{config.base_url.rstrip('/')}/oauth2/token"
    body = parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": config.client_id,
            "client_secret": config.client_secret,
        }
    ).encode("utf-8")

    token_request = request.Request(
        token_url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urlopen(token_request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Toss token request failed: HTTP {exc.code} {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Toss token request failed: {exc.reason}") from exc

    return TossToken(
        access_token=payload["access_token"],
        token_type=payload["token_type"],
        expires_in=int(payload["expires_in"]),
    )


def save_token(
    token: TossToken,
    *,
    token_dir: Path = TOKEN_DIR,
    issued_at: datetime | None = None,
) -> Path:
    issued_at = issued_at or datetime.now().astimezone()
    expires_at = issued_at + timedelta(seconds=token.expires_in)
    token_dir.mkdir(parents=True, exist_ok=True)

    token_path = token_dir / f"TOSS{issued_at.strftime('%Y%m%d_%H%M%S')}.json"
    payload = {
        "access_token": token.access_token,
        "token_type": token.token_type,
        "expires_in": token.expires_in,
        "issued_at": issued_at.isoformat(timespec="seconds"),
        "expires_at": expires_at.isoformat(timespec="seconds"),
    }
    token_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return token_path


def load_latest_token(token_dir: Path = TOKEN_DIR) -> dict[str, object] | None:
    token_files = sorted(token_dir.glob("TOSS*.json"))
    if not token_files:
        return None
    return json.loads(token_files[-1].read_text(encoding="utf-8"))


def ensure_daily_token(
    config: TossAuthConfig | None = None,
    *,
    token_dir: Path = TOKEN_DIR,
    now: datetime | None = None,
    issue_token_func: Callable[[TossAuthConfig], TossToken] = issue_token,
) -> Path:
    issued_at = now or datetime.now().astimezone()
    today_pattern = f"TOSS{issued_at.strftime('%Y%m%d')}_*.json"
    today_tokens = sorted(token_dir.glob(today_pattern))
    if today_tokens:
        return today_tokens[-1]

    token = issue_token_func(config or load_config())
    return save_token(token, token_dir=token_dir, issued_at=issued_at)


def _mask_token(token: str) -> str:
    if len(token) <= 12:
        return "*" * len(token)
    return f"{token[:6]}...{token[-6:]}"


def main() -> None:
    token_path = ensure_daily_token()
    token_payload = json.loads(token_path.read_text(encoding="utf-8"))
    print("Toss access token ready.")
    print(f"token_type: {token_payload['token_type']}")
    print(f"expires_in: {token_payload['expires_in']}")
    print(f"access_token: {_mask_token(token_payload['access_token'])}")
    print(f"saved_to: {token_path}")


if __name__ == "__main__":
    main()
