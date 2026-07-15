# File Configuration Adapter (`src/infrastructure/config.py`)

This infrastructure adapter owns JSON files under `~/KIS_config`.

- `ConfigFile` names portfolio, memo, strategy-history, strategy-config, and
  portfolio-weight files, including their read-only policy.
- `load_json()` returns the supplied default for a missing or unreadable file;
  callers can pass `strict=True` when a corrupt document must halt execution.
- `save_json()` rejects read-only files, writes through a same-directory
  temporary file, and atomically replaces the target after syncing it.

The composition root injects these file operations into application services;
domain modules do not import this adapter.
