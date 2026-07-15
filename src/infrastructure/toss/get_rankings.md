# Toss Rankings Query (`src/infrastructure/toss/get_rankings.py`)

`get_rankings()` reads the account-independent stock-ranking endpoint. It
validates the documented ranking type, market, duration, and page-size limits
before issuing a `RANKING`-group request.
