# Toss Order Query (`src/infrastructure/toss/get_order.py`)

`get_order()` reads one authenticated, account-scoped Toss order by ID and
returns the validated result object. It is the read seam for order status and
reconciliation; it does not modify the order.
