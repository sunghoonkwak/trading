# Google Sheets Portfolio Source Adapter

`portfolio_source.py` owns the Google Sheets connection and worksheet parsing
used by the portfolio infrastructure integration. The composition root injects
the private service-account file path through `configure_service_account_file()`.
The adapter returns the established normalized holdings, accounts, asset-info,
and cash-holdings shape.

The adapter is read-only. Connection failures retain the historical `None`
result and console message so portfolio integration can produce its normal
safe partial result.

## Responsibilities

1. Authenticate with the service-account file selected by the composition root.
2. Open the configured `financial portfolio` spreadsheet and its `USD` or
   `KRW` worksheet.
3. Normalize worksheet rows into `holdings`, `accounts`, `asset_info`, and
   `cash_holdings` source records.

## Public functions

### `connect_google_sheet(sheet_name)`

Returns the requested worksheet, or `None` after logging the established
connection failure message. It never writes to Google Sheets.

### `parse_worksheet_data(worksheet, currency)`

Parses the portfolio worksheet. Account names remain distinct keys, including
cash-only accounts. Sheet current-price values are deliberately ignored:
`infrastructure.portfolio.integration` supplies live Toss prices for GSheet
holdings.

```python
from infrastructure.gsheet import connect_google_sheet, parse_worksheet_data

worksheet = connect_google_sheet("USD")
source = parse_worksheet_data(worksheet, "USD") if worksheet else {}
```
