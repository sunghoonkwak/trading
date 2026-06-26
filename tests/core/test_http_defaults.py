import sys
from pathlib import Path
from types import SimpleNamespace


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


def test_install_requests_default_timeout_preserves_explicit_timeout():
    from core.http_defaults import install_requests_default_timeout

    calls = []

    def api_request(method, url, **kwargs):
        calls.append(("api", method, url, kwargs))
        return "api-response"

    def session_request(self, method, url, **kwargs):
        calls.append(("session", method, url, kwargs))
        return "session-response"

    fake_requests = SimpleNamespace(
        api=SimpleNamespace(request=api_request),
        Session=SimpleNamespace(request=session_request),
    )

    install_requests_default_timeout(fake_requests, default_timeout=12.5)

    assert fake_requests.api.request("GET", "https://example.test") == "api-response"
    assert fake_requests.api.request(
        "POST",
        "https://example.test",
        timeout=3.0,
    ) == "api-response"
    assert fake_requests.Session.request(
        object(),
        "GET",
        "https://example.test",
    ) == "session-response"

    assert calls == [
        ("api", "GET", "https://example.test", {"timeout": 12.5}),
        ("api", "POST", "https://example.test", {"timeout": 3.0}),
        ("session", "GET", "https://example.test", {"timeout": 12.5}),
    ]
