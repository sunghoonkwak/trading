# -*- coding: utf-8 -*-
"""Process-wide HTTP defaults for third-party request clients."""

from functools import wraps
from typing import Any


def install_requests_default_timeout(
    requests_module: Any = None,
    default_timeout: float = 30.0,
) -> None:
    """Install a process-wide default timeout for requests calls.

    Callers that pass an explicit ``timeout`` keep their chosen value.
    """
    if requests_module is None:
        import requests as requests_module

    original_request = requests_module.api.request
    if not getattr(original_request, "_trading_default_timeout", False):

        @wraps(original_request)
        def request_with_timeout(method, url, **kwargs):
            kwargs.setdefault("timeout", default_timeout)
            return original_request(method, url, **kwargs)

        request_with_timeout._trading_default_timeout = True
        requests_module.api.request = request_with_timeout

    original_session_request = requests_module.Session.request
    if not getattr(original_session_request, "_trading_default_timeout", False):

        @wraps(original_session_request)
        def session_request_with_timeout(self, method, url, **kwargs):
            kwargs.setdefault("timeout", default_timeout)
            return original_session_request(self, method, url, **kwargs)

        session_request_with_timeout._trading_default_timeout = True
        requests_module.Session.request = session_request_with_timeout
