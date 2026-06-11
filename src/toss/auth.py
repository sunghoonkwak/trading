from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable
from urllib import error, parse, request


DEFAULT_BASE_URL = "https://openapi.tossinvest.com"
DEFAULT_TIMEOUT = 10.0
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
TOKEN_DIR = Path(__file__).resolve().parents[2] / "token"


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


def _parse_env_file(env_path: Path) -> dict[str, str]:
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def _get_env_value(values: dict[str, str], key: str) -> str:
    return os.environ.get(key) or values.get(key, "")


def load_config(env_path: Path = ENV_PATH) -> TossAuthConfig:
    values = _parse_env_file(env_path)

    config = TossAuthConfig(
        client_id=_get_env_value(values, "TOSS_CLIENT_ID"),
        client_secret=_get_env_value(values, "TOSS_CLIENT_SECRET"),
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

    token_path = token_dir / f"toss_token_{issued_at.strftime('%Y%m%d_%H%M%S')}.json"
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
    token_files = sorted(token_dir.glob("toss_token_*.json"))
    if not token_files:
        return None
    return json.loads(token_files[-1].read_text(encoding="utf-8"))


def _mask_token(token: str) -> str:
    if len(token) <= 12:
        return "*" * len(token)
    return f"{token[:6]}...{token[-6:]}"


def main() -> None:
    token = issue_token(load_config())
    token_path = save_token(token)
    print("Toss access token issued.")
    print(f"token_type: {token.token_type}")
    print(f"expires_in: {token.expires_in}")
    print(f"access_token: {_mask_token(token.access_token)}")
    print(f"saved_to: {token_path}")


if __name__ == "__main__":
    main()
