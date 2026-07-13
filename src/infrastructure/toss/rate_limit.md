# Toss Rate Limiting (`src/infrastructure/toss/rate_limit.py`)

`TossRateLimitManager` coordinates per-group request spacing, records
rate-limit response headers, and calculates retry delays. The shared
`DEFAULT_RATE_LIMIT_MANAGER` is used by the Toss HTTP client so safe HTTP 429
retries respect the API's advertised limit.
