# Toss Strategy Trading Adapter

`infrastructure.toss.broker` adapts strategy trading operations to the Toss
Invest Open API.

## Responsibilities

- Returns `cashBuyingPower` as USD buying power for a strategy order.
- Converts `StrategyOrder` values to Toss order-creation arguments.
- Converts strategy `LOC` intent to Toss `LIMIT` with `timeInForce=CLS`.

## Boundaries

The adapter loads a token, selects the default account, and calls the Toss
HTTP helpers in this package. Actual order creation is reached only through
the configured strategy broker path. It preserves the existing order mapping
and failure result behavior.
