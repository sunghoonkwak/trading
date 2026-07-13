# Trading Configuration Adapter

`infrastructure.trading_configuration` owns stock metadata file I/O, KIS
market mapping, and KIS feature flags for
`src/infrastructure/stock_configuration.json`. Runtime and interface modules
load or save the
shared stock metadata through this adapter.
