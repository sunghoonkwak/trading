# File Configuration Adapter (`src/infrastructure/config.py`)

This infrastructure adapter owns JSON files under `~/KIS_config`.

- `ConfigFile` names portfolio, memo, strategy-history, strategy-config, and
  portfolio-weight files, including their read-only policy.
- `load_json()` returns the supplied default for a missing or unreadable file.
- `save_json()` rejects read-only files and returns `False` for other write
  failures.

The composition root injects these file operations into application services;
domain modules do not import this adapter.
