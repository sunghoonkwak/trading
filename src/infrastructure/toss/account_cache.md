# Toss Account Cache (`src/infrastructure/toss/account_cache.py`)

`get_default_account_seq()` obtains and process-caches the first Toss
`accountSeq` by access token and API base URL. `clear_default_account_cache()`
is the reset seam for tests and diagnostics. The cache contains no credentials
other than the in-memory lookup key and is never persisted.
