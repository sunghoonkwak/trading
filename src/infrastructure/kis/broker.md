# KIS Strategy Trading Adapter

`infrastructure.kis.broker` adapts strategy trading operations to the official
KIS API distribution under `infrastructure.kis.kis_api`.

## Responsibilities

- Reads `ovrs_ord_psbl_amt` from overseas buying-power results as orderable
  USD.
- Converts `StrategyOrder` `LIMIT` and `LOC` intents to KIS overseas order
  codes.
- Blocks KIS REST calls before authentication when
  `KIS_ENABLE_REST_API=false`.
- Returns a correlation-aware ambiguous result when an order call times out.

## Import boundary

KIS auth and endpoint wrappers are lazy-loaded at call time. Importing this
adapter does not read `KIS_config`, credentials, or token files.
