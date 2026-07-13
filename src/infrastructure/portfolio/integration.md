# Portfolio infrastructure integration

`integration.py` implements the normalized KIS, Toss, and Google Sheets
portfolio source merge and owns the in-memory Google Sheets cache. It is an
infrastructure adapter used by `application.portfolio_service.PortfolioService`
through the `PortfolioSource` contract.

The adapter preserves partial-error metadata and notification behavior. Local
alert publication and optional Telegram warnings are injected from `main.py`,
so this adapter does not import the legacy display or interface packages.

KIS reads cross the local `kis_source.py` adapter boundary. This keeps source
selection out of the merge implementation while preserving the established KIS
source result and partial-error behavior.

## Source and cache behavior

- `scope="kis"` queries KIS only; `scope="toss"` queries Toss only and uses
  the Toss exchange rate. Neither scope uses the Google Sheets fallback.
- `scope="all"` merges KIS with the cached Google Sheets source. A successful
  Toss source replaces the Google Sheets `토스` account; a Toss failure leaves
  that cached account in place and records `metadata.toss_error`.
- Google Sheets current-price values are discarded. Missing current prices are
  filled from Toss batch prices, and still-missing values become `0.0` with an
  injected operator warning.
- `refresh_gsheet_cache()` is the startup and `/gsheet` refresh operation. It
  replaces the cache only after a successful read; a failed refresh preserves
  an existing cache and returns counts, error text, and the last update time.

`merge_portfolio_sources()` assigns account IDs and produces the normalized
raw portfolio consumed by `PortfolioService`. The adapter keeps KIS, GSheet,
and Toss errors in metadata rather than hiding partial failures.
