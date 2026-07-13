# Stock Configuration Adapter

`infrastructure.stock_configuration` is the sole file-I/O boundary for
`src/stock_configuration.json`. Runtime and interface modules load or save the
shared stock metadata through this adapter.
