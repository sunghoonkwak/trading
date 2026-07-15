# Strategy history repository

This module owns the strategy-history JSON record format: order serialization,
strategy result construction, retry result merging, and persistence through the
injected `StrategyHistoryService`. Storage adapters remain outside this module.
