# Application Port Contracts (`src/application/ports/contracts.py`)

This module contains dependency-free contracts used by application services and
implemented by infrastructure adapters. It must not import concrete KIS, Toss,
or interface modules.

## Contracts

- `PortfolioSource` supplies normalized raw portfolio data.
- `SerializedKisOperations` performs one read-only KIS operation with timeout
  and correlation metadata.
- `PortfolioReader`, `MarketPriceReader`, and `OpenOrderReader` are read ports
  consumed by interfaces.
- `StrategyOrderExecutor` and `OrderControlService` define order execution and
  explicit order-control operations.
- `OperationResult` represents a value, redacted error, correlation ID, or
  ambiguous outcome; `redact_value()` masks account and credential fields.
