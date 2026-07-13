# Google Sheets Portfolio Source Adapter

`portfolio_source.py` owns the Google Sheets connection and worksheet parsing
used by the portfolio infrastructure integration. It reads the existing
service-account file through `CONFIG_ROOT` and returns the established
normalized holdings, accounts, asset-info, and cash-holdings shape.

The adapter is read-only. Connection failures retain the historical `None`
result and console message so portfolio integration can produce its normal
safe partial result.
