# KIS REST Client (`src/infrastructure/kis/rest_client.py`)

This infrastructure adapter authenticates KIS REST and WebSocket clients with
the existing bounded retry policy. It publishes authentication phase changes
through an optional callback injected by `main.py`; it does not import runtime
state directly.

`RESTClient.authenticate()` and `RESTClient.authenticate_ws()` retain their
existing result dictionaries and raise `KISAuthError` after retries are
exhausted.
