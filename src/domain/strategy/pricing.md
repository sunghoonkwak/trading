# Strategy Price Resolution (`src/domain/strategy/pricing.py`)

`resolve_current_price` is a pure strategy rule shared by domain calculations
and the strategy execution service.

- Prefer the explicit `current_prices[ticker]` value when it is positive.
- Otherwise use `holding["cur_price"]`.
- Return `0.0` when neither source provides a positive value; the calling
  strategy handles its existing skip or error behavior.
