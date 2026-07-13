import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


def test_rest_client_publishes_authentication_state_through_adapter(monkeypatch):
    from infrastructure.kis import kis_rest_client

    states = []
    kis_rest_client.configure_state_publisher(
        lambda phase, error=None: states.append((phase, error))
    )
    monkeypatch.setattr(kis_rest_client.ka, "auth", lambda: None)

    assert kis_rest_client.RESTClient.authenticate() == {"status": "authenticated"}
    assert states == [
        ("authenticating", None),
        ("authenticated", None),
    ]


def test_rest_client_publishes_failed_authentication_state(monkeypatch):
    from infrastructure.kis import kis_rest_client

    states = []
    kis_rest_client.configure_state_publisher(
        lambda phase, error=None: states.append((phase, error))
    )
    monkeypatch.setattr(
        kis_rest_client.ka,
        "auth",
        lambda: (_ for _ in ()).throw(RuntimeError("authentication failed")),
    )
    monkeypatch.setattr(kis_rest_client.time, "sleep", lambda _delay: None)

    with pytest.raises(kis_rest_client.KISAuthError, match="authentication failed"):
        kis_rest_client.RESTClient.authenticate()

    assert states == [
        ("authenticating", None),
        ("failed", "authentication failed"),
    ] * 3
