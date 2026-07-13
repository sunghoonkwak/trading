# Strategy value types

`base.py` defines the broker-independent strategy value types. `OrderSide`
expresses buy, sell, or hold intent; `StrategyStatus` records executed,
partial, skipped, disabled, error, and duplicate-safe outcomes.

`StrategyOrder` carries symbol, side, quantity, price, order type, and reason.
Domain strategies create this value; infrastructure adapters translate it to a
broker-specific request.
