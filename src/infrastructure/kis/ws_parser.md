# KIS WebSocket Record Helpers (`src/infrastructure/kis/ws_parser.py`)

This module normalizes vendor WebSocket records and creates safe diagnostics.
It does not send notifications or import Telegram.

- `normalize_record()` pads or truncates a record to its configured columns and
  returns a drift note.
- `split_records()` separates multi-record payloads while preserving a single
  malformed record for diagnostics.
- `mask_record_for_log()` and `mask_dict_for_log()` hide account and order
  fields; `build_schema_drift_alert()` never includes raw record values.
- `should_log_normalization()` and `should_send_schema_drift_alert()` suppress
  expected truncation noise and rate-limit drift alerts per TR ID.
