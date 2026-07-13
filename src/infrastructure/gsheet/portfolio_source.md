# Google Sheets Portfolio Source Adapter

`portfolio_source.py` owns the Google Sheets connection, worksheet parsing,
and in-memory source cache used by the portfolio infrastructure integration.
The composition root injects the private service-account file path through
`configure_service_account_file()`. The adapter returns the established
normalized holdings, accounts, asset-info, and cash-holdings shape.

The adapter is read-only. Connection failures retain the historical `None`
result and console message so portfolio integration can produce its normal
safe partial result.

## Responsibilities

1. Authenticate with the service-account file selected by the composition root.
2. Open the configured `financial portfolio` spreadsheet and its `USD` or
   `KRW` worksheet.
3. Normalize worksheet rows into `holdings`, `accounts`, `asset_info`, and
   `cash_holdings` source records.
4. Cache completed source reads and retain the last safe cache on exceptions.

## Public functions

### `connect_google_sheet(sheet_name)`

Returns the requested worksheet, or `None` after logging the established
connection failure message. It never writes to Google Sheets.

### `parse_worksheet_data(worksheet, currency)`

Parses the portfolio worksheet. Account names remain distinct keys, including
cash-only accounts. Sheet current-price values are deliberately ignored:
`infrastructure.portfolio.integration` supplies live Toss prices for GSheet
holdings.

### Cache lifecycle

`get_cached_portfolio()` loads the source once, then returns a defensive copy.
`refresh_portfolio_cache()` replaces the cache after a completed fetch,
including a partial source paired with an error. An exception preserves the
previous source and reports its last update time. `invalidate_portfolio_cache()`
clears all cached data for an explicit refresh or test reset.

```python
from infrastructure.gsheet import connect_google_sheet, parse_worksheet_data

worksheet = connect_google_sheet("USD")
source = parse_worksheet_data(worksheet, "USD") if worksheet else {}
```
