# Toss Orders Query (`src/infrastructure/toss/get_orders.py`)

`get_orders()` reads the authenticated, account-scoped Toss order list with
its supported status and pagination filters. It returns the API result object
and does not modify orders.
