# Toss Candles Query (`src/infrastructure/toss/get_candles.py`)

`get_candles()` reads `GET /api/v1/candles` for a symbol with `1m` or `1d`
intervals. It supports count, cursor (`before`), and adjusted-price options,
then returns the validated result object.
