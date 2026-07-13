# Toss Accounts Query (`src/infrastructure/toss/get_accounts.py`)

`get_accounts()` reads `GET /api/v1/accounts` through the shared Toss client
and returns the API result list. Its `accountSeq` values are used by account-
scoped portfolio and order helpers.
