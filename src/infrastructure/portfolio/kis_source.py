"""KIS portfolio-source adapter boundary."""

from typing import Any


def fetch_kis_portfolio_source() -> tuple[dict[str, Any], dict[str, Any]]:
    """Read the established KIS portfolio source through its compatibility API."""
    from broker.kis_portfolio import fetch_kis_portfolio

    return fetch_kis_portfolio()
