# Advanced Python Testing Design

## Goal

Extend the existing Ruff, mypy, and pytest checks with risk-focused testing
for a real-time trading system. The additions must run without live
credentials, network access, or order submission.

## Delivery Strategy

Adopt the checks in two stages. Stage 1 adds inexpensive checks to the normal
developer and CI loop. Stage 2 adds deeper diagnostics without immediately
making unstable metrics such as mutation score or total coverage percentage
blocking requirements.

## Stage 1

### Coverage

Add `pytest-cov` to the development dependencies and run the existing suite
with source coverage in CI. Report missing lines, but do not set a global
minimum initially. This establishes an honest baseline without encouraging
low-value tests solely to satisfy a percentage.

### Property-Based Tests

Add `hypothesis` and durable tests under the existing module-oriented test
directories. Begin with pure strategy and order-calculation boundaries where
generated prices, quantities, exchange rates, and available cash can verify
these invariants:

- submitted quantities are positive;
- calculated spend does not exceed the allowed budget;
- invalid or zero prices do not produce executable orders;
- replaying completed strategy history does not create duplicate orders.

Generated examples must not call KIS, Toss, Telegram, Google Sheets, or the
network.

### Dependency Audit

Add `pip-audit` to the development toolchain and run it in CI after dependency
installation. Audit failures are blocking because known vulnerable runtime
dependencies are actionable. If the current dependency set contains an
unfixable advisory, document and pin a narrowly scoped ignore with the
advisory identifier and reason rather than disabling the audit.

## Stage 2

### Mutation Testing

Add `mutmut` as an opt-in local diagnostic focused on application-owned
strategy and broker modules. Do not mutate `src/infrastructure/kis/kis_api/**`. Document a
repeatable command, but do not make mutation score a blocking CI threshold
until the baseline and runtime are known.

### API Response Replay

Add sanitized JSON fixtures for representative KIS and Toss REST responses and
plain-text fixtures for WebSocket records. Fixtures must contain dummy account
numbers and tokens only. Replay tests will exercise existing app-owned parsers
and broker facades entirely offline, including:

- normal responses;
- missing and null fields;
- error responses;
- truncated and extended WebSocket records.

No new generic replay framework will be introduced unless existing parser
interfaces cannot consume fixtures directly.

### Docker Smoke Check

Add a CI job that builds the service image and runs the test suite inside the
container image or Compose service without starting live trading. It must not
mount private `KIS_config`, authenticate, start `src/main.py`, or expose order
endpoints. The check validates dependency installation, imports, and test
behavior in the production Python environment.

## CI Flow

The default quality flow is:

1. install development dependencies;
2. run Ruff;
3. run mypy;
4. run pytest with coverage reporting;
5. run `pip-audit`;
6. run the isolated Docker smoke job.

Mutation testing remains an explicit local or scheduled diagnostic. API replay
tests are part of normal pytest once added.

## Documentation

Update the README with exact host, Docker, coverage, audit, property-test, and
mutation commands. Clarify which checks are blocking and which are diagnostic.

## Success Criteria

- The existing 186 tests continue to pass.
- Property tests exercise real pure functions and run without external calls.
- Coverage is reported locally and in CI without an initial percentage gate.
- Dependency auditing passes or has a documented advisory-specific exception.
- Replay fixtures contain no credentials or private account data.
- Docker verification does not start the trading runtime or submit orders.
- Ruff and mypy remain green.

## Out of Scope

- Live brokerage integration tests.
- Automated paper or real orders.
- A global coverage or mutation score threshold before measuring a baseline.
- Changes inside the official KIS distribution tree.
