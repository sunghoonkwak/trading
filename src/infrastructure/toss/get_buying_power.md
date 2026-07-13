# Toss Buying-Power Query (`src/infrastructure/toss/get_buying_power.py`)

`get_buying_power()` reads `GET /api/v1/buying-power` for `KRW` or `USD` and
requires an account sequence, access token, and `X-Tossinvest-Account` header.
It returns the API result object, including cash buying power.
