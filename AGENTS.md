# Repository Guidelines

## Project Layout

This is a Python 3.9+ KIS real-time trading system. Runtime entry point:
`src/main.py`.

- `src/core/`: configuration and web support
- `src/kis/`: Korea Investment Securities API integration and official KIS
  sample/vendor-like code
- `src/strategy/`: RAOEO, value averaging, rebalancing, and execution
- `src/scheduler/`, `src/telegram_bot/`, `src/data/`, `src/state/`,
  `src/utils/`: supporting services
- `src/broker/`: application-owned broker facades around external trading APIs
- `src/web/static/`: web assets
- `templates/`: sample configuration only
- `scripts/backtest/raoeo/`: backtest tooling

Private runtime configuration belongs in `KIS_config/` or an external mount.

## Runtime And Commands

The trading runtime is Docker-only. Do not run `python src/main.py` on the
host; it is guarded to prevent conflicts with the managed container.

- `docker compose up -d --build`: build and start the bot on port `8080`.
- `docker compose restart trading-bot`: restart after source changes.
- `docker logs -f my-trading-bot`: follow startup and live logs.
- `docker compose exec trading-bot python -m pytest tests`: run tests in Docker.
- `venv/bin/pytest tests`: run safe host-side tests first when appropriate.
- `venv/bin/python scripts/validate_config.py`: validate configuration.
- `venv/bin/python scripts/backtest/raoeo/backtest_raoeo.py`: run backtests.

For host-side development use `venv/bin/python` and `venv/bin/pytest`; do not
probe system Python first unless the virtualenv is missing or explicitly
requested.

## Live KIS Diagnostics

For live KIS REST diagnosis, prefer a read-only one-off query in the running
container over temporary runtime logging or a service restart.

- Use KIS Coding Assistant MCP first to identify the intended API and response
  field.
- Run application imports from the package root:
  `docker compose exec -T -w /app/src trading-bot python ...`.
  `/app` is the mounted repository root; `/app/src` is the Python import root.
- A one-off `docker compose exec` Python process does not share in-memory
  authentication with the running daemon. In that process call `ka.auth()`
  before `ka.getTREnv()` or account REST calls.
- For overseas buying power, use `inquire_psamount` field
  `ovrs_ord_psbl_amt`; do not infer orderable USD from portfolio cash or
  withdrawal-available balance fields.
- Keep diagnostics read-only and never print or persist credentials, account
  numbers, tokens, or unmasked sensitive payloads.

## Toss API Reference

For Toss Invest Open API work, consult the checked-in OpenAPI reference first:
`docs/reference/toss-openapi.json`. It is a public-style API schema with
dummy examples only; runtime credentials and account data still belong only in
`KIS_config/` or external mounts.

- Implement Toss helpers under `src/toss/` and keep orchestration in app-owned
  modules such as `src/broker/`.
- Use the schema to confirm paths, methods, request body `Content-Type`,
  required headers such as `X-Tossinvest-Account`, and response field names
  before changing Toss API calls.
- Keep live Toss diagnostics read-only unless the user explicitly asks for an
  order-changing action such as create, modify, or cancel.

## Coding And Documentation

Use standard Python style: 4-space indentation, `snake_case` functions and
variables, and `PascalCase` classes. Keep services focused and prefer existing
helpers in `src/utils`, `src/state`, and `src/core`.

Keep changes surgical and goal-driven. Every changed line should trace directly
to the requested trading-system behavior, its tests, or matching operational
documentation. Prefer the simplest working change over speculative flexibility
or one-off abstractions.

Many modules have matching `.md` notes beside `.py` files. Update them when
behavior or operational expectations change. Do not hand-edit generated or
vendor-like KIS endpoint wrappers unless intentionally scoped.

Treat `src/kis/kis_api/**` as the official Korea Investment Securities API
distribution boundary. Keep application policy, orchestration, and testing
seams outside that tree, preferably in `src/broker/`, `src/strategy/`,
`src/data/`, or other app-owned modules. Changes inside the official KIS tree
should be limited to deliberate compatibility/security patches that are worth
reapplying during upstream updates.

## Testing

Keep durable regression tests under module-oriented directories such as
`tests/kis/`, `tests/toss/`, `tests/raoeo/`, `tests/telegram/`, `tests/data/`,
`tests/core/`, and `tests/scheduler/`. Use descriptive `test_*.py` filenames
inside those directories, and avoid splitting one behavior area into many tiny
files.

When creating temporary tests only to guide an implementation or debug a
one-off issue, put them under `tests/tmp/`. Treat that directory as scratch
space: run the temporary tests while working, then either promote useful
regression coverage into the relevant module directory or delete the temporary
files before shipping. Do not rely on `tests/tmp/` for permanent coverage.

Strategy, formatter, and state tests should avoid live KIS, Telegram, or market
calls. For strategy changes, run the relevant tests and backtest scripts; before
shipping, run `docker compose exec trading-bot python -m pytest tests`.

## Commits And Pull Requests

Use Conventional Commits with scopes, such as `feat(raoeo): ...` or
`fix(telegram): ...`. The subject line MUST be 50 characters or less and body
lines MUST wrap at 72 characters or less. Confirm the subject length before
suggesting or creating a commit.

For non-trivial commits, use focused bullets explaining behavior and impact:

```text
type(scope): concise subject

- Explain the behavior change and why it matters.
- Mention verification, configuration, or operational impact.
```

Pull requests should describe behavior changes and verification, link related
issues, and include screenshots or logs for dashboard, Telegram, or
scheduler-visible changes. Optional local enforcement:
`git config commit.template .gitmessage` and
`git config core.hooksPath .githooks`.

## Security

Never commit API keys, account numbers, Telegram tokens, generated
credentials, logs, `.env` files, or private `KIS_config/` contents. Use
`templates/` for examples and mounts for private configuration. Test changes
with mock or paper-trading accounts before enabling live automation.
