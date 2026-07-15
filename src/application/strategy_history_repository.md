# Strategy history repository

This module owns the strategy-history JSON record format: order serialization,
strategy result construction, retry result merging, and persistence through the
injected `StrategyHistoryService`. It also serializes manual RAOEO cash-funding
results. Storage adapters remain outside this module.
