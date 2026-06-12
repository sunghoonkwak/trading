import json
import sys
import unittest
from pathlib import Path
from urllib import error, request


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class TossRateLimitTest(unittest.TestCase):
    def test_request_json_retries_429_after_retry_after(self):
        from toss.client import request_json
        from toss.rate_limit import TossRateLimitManager

        clock = FakeClock()
        manager = TossRateLimitManager(
            sleep_func=clock.sleep,
            monotonic_func=clock.monotonic,
            jitter_func=lambda _start, _end: 0.0,
        )
        calls = []

        def fake_urlopen(api_request, timeout):
            calls.append((api_request.full_url, timeout))
            if len(calls) == 1:
                raise error.HTTPError(
                    api_request.full_url,
                    429,
                    "Too Many Requests",
                    {"Retry-After": "2", "X-RateLimit-Limit": "1", "X-RateLimit-Remaining": "0"},
                    None,
                )
            return FakeResponse(
                {"result": {"ok": True}},
                headers={"X-RateLimit-Limit": "1", "X-RateLimit-Remaining": "0"},
            )

        payload = request_json(
            request.Request("https://example.test/api/v1/orders", method="GET"),
            group="ORDER",
            action_name="orders",
            timeout=10.0,
            urlopen=fake_urlopen,
            rate_limiter=manager,
            max_retries=1,
        )

        self.assertEqual(payload["result"], {"ok": True})
        self.assertEqual(len(calls), 2)
        self.assertEqual(clock.sleeps, [2.0])

    def test_rate_limiter_uses_response_limit_headers_before_next_request(self):
        from toss.rate_limit import TossRateLimitManager

        clock = FakeClock()
        manager = TossRateLimitManager(
            sleep_func=clock.sleep,
            monotonic_func=clock.monotonic,
            jitter_func=lambda _start, _end: 0.0,
        )

        manager.update_from_headers(
            "ACCOUNT",
            {
                "X-RateLimit-Limit": "1",
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": "1",
            },
        )
        manager.wait("ACCOUNT")

        self.assertEqual(clock.sleeps, [1.0])


class FakeResponse:
    def __init__(self, payload, headers=None):
        self.payload = payload
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


if __name__ == "__main__":
    unittest.main()
