# Toss Prices Query (`src/infrastructure/toss/get_prices.py`)

`get_prices()` reads current Toss prices for one or more symbols and returns
the validated result list. `infrastructure.market_data` uses it as the
Toss-first batch-price source before falling back to KIS.
