# Portfolio infrastructure integration

`integration.py` implements the normalized KIS, Toss, and Google Sheets
portfolio source merge. The Google Sheets adapter owns its in-memory cache;
this module retains forwarding functions for the established refresh and test
seams. It is an infrastructure adapter used by
`application.portfolio_service.PortfolioService` through the `PortfolioSource`
contract.

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
  delegates cache ownership to `infrastructure.gsheet.portfolio_source`.
  A completed partial read replaces the cache with its error metadata; an
  exception preserves the existing cache and returns counts, error text, and
  the last update time.

`merge_portfolio_sources()` assigns account IDs and produces the normalized
raw portfolio consumed by `PortfolioService`. The adapter keeps KIS, GSheet,
and Toss errors in metadata rather than hiding partial failures.
