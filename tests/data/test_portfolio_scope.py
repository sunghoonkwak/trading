import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from domain.portfolio.scope import normalize_portfolio_scope


@pytest.mark.parametrize(
    ("scope", "expected"),
    [
        (None, "all"),
        ("", "all"),
        (0, "all"),
        (" KIS ", "kis"),
        ("ToSs", "toss"),
    ],
)
def test_normalize_portfolio_scope_normalizes_supported_values(scope, expected):
    assert normalize_portfolio_scope(scope) == expected


@pytest.mark.parametrize("scope", ["broker", "paper"])
def test_normalize_portfolio_scope_rejects_unknown_values(scope):
    with pytest.raises(ValueError, match="portfolio scope"):
        normalize_portfolio_scope(scope)
