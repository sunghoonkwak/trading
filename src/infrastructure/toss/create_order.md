# Toss Create-Order Helper (`src/infrastructure/toss/create_order.py`)

`create_order()` sends `POST /api/v1/orders` with the required account header
and JSON body. It supports quantity or order amount, limit/market fields,
client order IDs, and explicit high-value-order confirmation. The CLI previews
the request unless `--execute` is supplied.
