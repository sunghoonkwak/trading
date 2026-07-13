import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))


def test_rest_client_publishes_authentication_state_through_adapter(monkeypatch):
    from infrastructure.kis import rest_client

    states = []
    rest_client.configure_state_publisher(
        lambda phase, error=None: states.append((phase, error))
    )
    monkeypatch.setattr(rest_client.ka, "auth", lambda: None)

    assert rest_client.RESTClient.authenticate() == {"status": "authenticated"}
    assert states == [
        ("authenticating", None),
        ("authenticated", None),
    ]


def test_rest_client_publishes_failed_authentication_state(monkeypatch):
    from infrastructure.kis import rest_client

    states = []
    rest_client.configure_state_publisher(
        lambda phase, error=None: states.append((phase, error))
    )
    monkeypatch.setattr(
        rest_client.ka,
        "auth",
        lambda: (_ for _ in ()).throw(RuntimeError("authentication failed")),
    )
    monkeypatch.setattr(rest_client.time, "sleep", lambda _delay: None)

    with pytest.raises(rest_client.KISAuthError, match="authentication failed"):
        rest_client.RESTClient.authenticate()

    assert states == [
        ("authenticating", None),
        ("failed", "authentication failed"),
    ] * 3
