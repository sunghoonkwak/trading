# Toss Commissions Query (`src/infrastructure/toss/get_commissions.py`)

`get_commissions()` reads the Toss commission estimate for a symbol and order
parameters through the shared authenticated client. It returns the API result
object and does not place an order.
