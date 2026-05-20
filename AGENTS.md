# Repository Guidelines

## Project Structure & Module Organization

This is a Python 3.9+ KIS real-time trading system. The runtime entry point is `src/main.py`. Core application modules live under `src/`: `core/` for configuration and web support; `kis/` for Korea Investment Securities API integration; `strategy/` for RAOEO, value averaging, rebalancing, and execution services; `scheduler/`, `telegram_bot/`, `data/`, `state/`, and `utils/` for supporting services. Web assets are under `src/web/static`, sample configuration lives in `templates/`, and backtest tooling is under `scripts/backtest/raoeo/`. Private runtime configuration belongs in `KIS_config/` or an external mount.

## Build, Test, and Development Commands

- `docker compose up -d --build`: build and start the bot container on port `8080`.
- `docker logs -f my-trading-bot`: follow container logs during startup and live trading.
- `docker compose exec trading-bot python -m pytest tests`: run tests inside the running container.
- `python scripts/backtest/raoeo/backtest_raoeo.py`: run the RAOEO backtest script.

The trading runtime is Docker-only. Do not run `python src/main.py` directly
from the host; `src/main.py` blocks non-Docker startup so local processes do
not conflict with the managed container.

## Coding Style & Naming Conventions

Use standard Python style with 4-space indentation, `snake_case` for functions, variables, and modules, and `PascalCase` for classes. Keep service modules focused and prefer existing helpers from `src/utils`, `src/state`, and `src/core`. Many modules have matching `.md` notes beside `.py` files; update these when behavior or operational expectations change. Do not hand-edit generated or vendor-like KIS endpoint wrappers unless intentionally scoped.

## Testing Guidelines

The repository has a `tests/` directory but no committed pytest config yet. Add tests under `tests/` using `test_*.py` files and descriptive test function names. For strategy, formatter, and state logic, prefer deterministic unit tests that avoid live KIS, Telegram, or market calls. When introducing pytest tests, run `docker compose exec trading-bot python -m pytest tests`; also run relevant backtest scripts for strategy changes.

## Commit & Pull Request Guidelines

Recent history uses Conventional Commits with scopes, for example `feat(raoeo): ...`, `fix(telegram): ...`, `docs(backtest): ...`, and `refactor(backtest): ...`. Follow the 50/72 rule: the subject line MUST be 50 characters or less, and body lines MUST wrap at 72 characters or less. Before suggesting or creating a commit, count the subject length and confirm it is within the limit. Prefer bullet-point bodies for multi-part changes:

```text
type(scope): concise subject

- Explain the first concrete behavior change.
- Explain the second change or operational impact.
- Mention config, tests, docs, or migration effects.
```

Keep each bullet focused on why the change matters, not just which files changed. Pull requests should describe behavior changes, list verification, link related issues, and include screenshots or logs for dashboard, Telegram, or scheduler-visible changes.

This repository provides `.gitmessage` and `.githooks/commit-msg` to help enforce these rules locally. Enable them with `git config commit.template .gitmessage` and `git config core.hooksPath .githooks`.

## Security & Configuration Tips

Never commit API keys, account numbers, Telegram tokens, generated credentials, logs, or local `.env` files. Use `templates/` for examples and mount private files into `KIS_config/`, as shown in `docker-compose.yml`. Test changes against mock or paper-trading accounts before enabling live automation.
