# -*- coding: utf-8 -*-
"""Shared portfolio scope constants and validation."""

PORTFOLIO_SCOPE_ALL = "all"
PORTFOLIO_SCOPE_KIS = "kis"
PORTFOLIO_SCOPE_TOSS = "toss"

PORTFOLIO_SCOPES = {
    PORTFOLIO_SCOPE_ALL,
    PORTFOLIO_SCOPE_KIS,
    PORTFOLIO_SCOPE_TOSS,
}


def normalize_portfolio_scope(scope: str) -> str:
    """Return a validated portfolio scope string."""
    normalized = str(scope or PORTFOLIO_SCOPE_ALL).strip().lower()
    if normalized not in PORTFOLIO_SCOPES:
        raise ValueError(
            "portfolio scope must be one of: "
            f"{', '.join(sorted(PORTFOLIO_SCOPES))}"
        )
    return normalized
