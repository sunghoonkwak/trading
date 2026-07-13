# Toss Cancel-Order Helper (`src/infrastructure/toss/cancel_order.py`)

`cancel_order()` sends `POST /api/v1/orders/{orderId}/cancel` with the required
Toss account header. The CLI is dry-run by default and submits only with
`--execute`.
