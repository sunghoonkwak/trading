# Toss Holdings Query (`src/infrastructure/toss/get_holdings.py`)

`get_holdings()` reads the authenticated, account-scoped Toss holdings endpoint
and returns its result object. `infrastructure.toss.portfolio` converts this
response into the application's normalized portfolio-source shape.
