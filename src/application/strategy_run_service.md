# Strategy Run Services (`src/application/strategy_run_service.py`)

These application-facing services expose configured strategy execution without
binding callers to concrete brokers, configuration, or persistence adapters.

## Services

- `StrategyRunService` delegates RAOEO, Value Averaging, rebalancing, and the
  shared RAOEO/Value Averaging suite to injected callables.
- `StrategyMarketDataService` loads the configured broker-scoped portfolio and
  fills missing strategy prices through an injected reader.
- `StrategyHistoryService` validates the list-shaped history document, clears a
  date entry, and upserts one strategy result while retaining the newest 200
  dates. A failed save raises `StrategyHistoryPersistenceError`, so callers
  cannot treat an unrecorded order result as durable state.
