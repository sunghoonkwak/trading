from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Mapping
from urllib import parse, request

from core.constants import CONFIG_ROOT
from core.credentials import load_credentials
from toss.client import request_json


DEFAULT_BASE_URL = "https://openapi.tossinvest.com"
DEFAULT_TIMEOUT = 10.0
CONFIG_ROOT_PATH = Path(CONFIG_ROOT)
TOKEN_DIR = CONFIG_ROOT_PATH
TOKEN_EXPIRY_SAFETY_MARGIN = timedelta(minutes=1)


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

    payload = request_json(
        token_request,
        group="AUTH",
        action_name="token",
        timeout=timeout,
        urlopen=urlopen,
    )

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


def token_expires_at(token_payload: Mapping[str, object]) -> datetime | None:
    expires_at = token_payload.get("expires_at")
    if isinstance(expires_at, str) and expires_at:
        parsed = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.astimezone()

    issued_at = token_payload.get("issued_at")
    expires_in = token_payload.get("expires_in")
    if isinstance(issued_at, str) and expires_in is not None:
        parsed_issued_at = datetime.fromisoformat(issued_at.replace("Z", "+00:00"))
        if parsed_issued_at.tzinfo is None:
            parsed_issued_at = parsed_issued_at.astimezone()
        return parsed_issued_at + timedelta(seconds=int(expires_in))

    return None


def is_token_expired(
    token_payload: Mapping[str, object],
    *,
    now: datetime | None = None,
    safety_margin: timedelta = TOKEN_EXPIRY_SAFETY_MARGIN,
) -> bool:
    expires_at = token_expires_at(token_payload)
    if expires_at is None:
        return False

    checked_at = now or datetime.now(expires_at.tzinfo).astimezone(expires_at.tzinfo)
    if checked_at.tzinfo is None:
        checked_at = checked_at.astimezone()
    checked_at = checked_at.astimezone(expires_at.tzinfo)
    return expires_at <= checked_at + safety_margin


def ensure_valid_token(
    config: TossAuthConfig | None = None,
    *,
    token_dir: Path = TOKEN_DIR,
    now: datetime | None = None,
    issue_token_func: Callable[[TossAuthConfig], TossToken] = issue_token,
) -> dict[str, object]:
    token_payload = load_latest_token(token_dir)
    if not token_payload:
        raise RuntimeError("No saved Toss token found. Run src/toss/auth.py first.")

    if not is_token_expired(token_payload, now=now):
        return token_payload

    expires_at = token_expires_at(token_payload)
    expires_text = expires_at.isoformat(timespec="seconds") if expires_at else "unknown"
    logging.warning(
        "[TossAuth] saved Toss token expired at %s; issuing a new token",
        expires_text,
    )

    issued_at = now or datetime.now().astimezone()
    token = issue_token_func(config or load_config())
    token_path = save_token(token, token_dir=token_dir, issued_at=issued_at)
    logging.info("[TossAuth] renewed expired Toss token: %s", token_path)
    return json.loads(token_path.read_text(encoding="utf-8"))


def load_access_token(
    token_dir: Path = TOKEN_DIR,
    *,
    config: TossAuthConfig | None = None,
    now: datetime | None = None,
    issue_token_func: Callable[[TossAuthConfig], TossToken] = issue_token,
) -> str:
    token_payload = ensure_valid_token(
        config=config,
        token_dir=token_dir,
        now=now,
        issue_token_func=issue_token_func,
    )
    access_token = token_payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise RuntimeError("Saved Toss token file does not contain access_token.")
    return access_token


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
        latest_today = today_tokens[-1]
        token_payload = json.loads(latest_today.read_text(encoding="utf-8"))
        if not is_token_expired(token_payload, now=issued_at):
            return latest_today

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
