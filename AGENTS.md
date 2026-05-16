# Repository Guidelines

## Project Structure & Module Organization

This is a Python 3.9+ KIS real-time trading system. The runtime entry point is `src/main.py`. Core application modules live under `src/`: `core/` for configuration and web support; `kis/` for Korea Investment Securities API integration; `strategy/` for RAOEO, value averaging, rebalancing, and execution services; `scheduler/`, `telegram_bot/`, `data/`, `state/`, and `utils/` for supporting services. Web assets are under `src/web/static`, sample configuration lives in `templates/`, and backtest tooling is under `scripts/backtest/raoeo/`. Private runtime configuration belongs in `KIS_config/` or an external mount.

## Build, Test, and Development Commands

- `python -m venv venv && source venv/bin/activate`: create and activate a local environment.
- `pip install -r requirements.txt`: install runtime dependencies.
- `python src/main.py`: run the trading system locally; requires valid KIS and Telegram configuration.
- `docker compose up -d --build`: build and start the bot container on port `8080`.
- `docker logs -f my-trading-bot`: follow container logs during startup and live trading.
- `python scripts/backtest/raoeo/backtest_raoeo.py`: run the RAOEO backtest script.

## Coding Style & Naming Conventions

Use standard Python style with 4-space indentation, `snake_case` for functions, variables, and modules, and `PascalCase` for classes. Keep service modules focused and prefer existing helpers from `src/utils`, `src/state`, and `src/core`. Many modules have matching `.md` notes beside `.py` files; update these when behavior or operational expectations change. Do not hand-edit generated or vendor-like KIS endpoint wrappers unless intentionally scoped.

## Testing Guidelines

The repository has a `tests/` directory but no committed test suite or pytest config yet. Add tests under `tests/` using `test_*.py` files and descriptive test function names. For strategy, formatter, and state logic, prefer deterministic unit tests that avoid live KIS, Telegram, or market calls. When introducing pytest tests, run `python -m pytest tests`; also run relevant backtest scripts for strategy changes.

## Commit & Pull Request Guidelines

Recent history uses Conventional Commits with scopes, for example `feat(raoeo): ...`, `fix(telegram): ...`, `docs(backtest): ...`, and `refactor(backtest): ...`. Follow the 50/72 rule: keep the subject line at 50 characters or less when practical, and wrap body text at 72 characters. Prefer bullet-point bodies for multi-part changes:

```text
type(scope): concise subject

- Explain the first concrete behavior change.
- Explain the second change or operational impact.
- Mention config, tests, docs, or migration effects.
```

Keep each bullet focused on why the change matters, not just which files changed. Pull requests should describe behavior changes, list verification, link related issues, and include screenshots or logs for dashboard, Telegram, or scheduler-visible changes.

## Security & Configuration Tips

Never commit API keys, account numbers, Telegram tokens, generated credentials, logs, or local `.env` files. Use `templates/` for examples and mount private files into `KIS_config/`, as shown in `docker-compose.yml`. Test changes against mock or paper-trading accounts before enabling live automation.
