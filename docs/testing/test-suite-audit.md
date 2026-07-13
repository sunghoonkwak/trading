# Test Suite Audit

**Status:** Audit work complete — full offline verification complete; the
accepted rebalancing policy and KIS duplicate-event safeguard are documented.

**Scope:** All 26 `tests/**/test_*.py` modules present on 2026-07-10.
The assessment is static: it reads test contracts, seams, and matching
application-owned code. It does not treat line count, assertion count, or
coverage lines as a reason to remove a test.

## Decision Rules

| Rule | Decision outcome |
| --- | --- |
| A test covers a distinct user-visible, safety, ordering, import, or failure contract. | Retain; setup may still be simplified. |
| Tests have the same input class, failure mode, and observable outcome. | Merge through parameterization or leave one representative. |
| A test only asserts a private name or removed implementation symbol. | Remove unless an explicit public/boundary contract requires it. |
| A test recreates the production formula. | Prefer independent examples or invariants. |
| A test touches files, credentials, network, broker, or order seams. | Keep all inputs injected and sanitized; static audit blocks any live route. |

## Static Safety Check

No reviewed test is intended to start `src/main.py`, authenticate, submit an
order, or use real credentials. The suite relies on injected `urlopen`/request
seams, fakes, and `monkeypatch`. The subprocess checks in
`tests/architecture/test_boundaries.py` execute local imports only. U4 must
confirm this with the full offline suite and Docker test service.

## Module Inventory

`Action` describes the next audit action, not an already-approved source or
test change. “Retain” means no overlap was found at module level; individual
tests can still be simplified in U2.

| Test module | Protected contract / matching area | Setup or overlap observation | Action |
| --- | --- | --- | --- |
| `tests/architecture/test_boundaries.py` | Importing app packages does not initialize KIS configuration, runtime modules, Telegram bot modules, or prohibited legacy dependencies; market status uses the public contract. | Ten subprocess/import checks cover different forbidden side effects and already share `_run_import_check`. | Retain. Do not merge solely for shared subprocess setup. |
| `tests/core/test_event_pipe.py` | Unix-socket log forwarding handles queue limits, disconnects, reset scheduling, send/receive buffering, and socket failures. | Autouse module-state reset is justified by module globals; fake socket centralizes I/O behavior. | Retain; review only whether reset fields track current state. |
| `tests/core/test_http_defaults.py` | Default HTTP timeout is supplied without overwriting an explicit caller timeout for module and session requests. | One focused fake-request contract. | Retain. |
| `tests/core/test_runtime.py` | Credentials parse current and legacy values; config validation fails safely; web actions are gated; KIS/runtime lifecycle fails closed and remains controllable. | Two credential tests manually manage fixed `tests/.tmp-*` paths; lifecycle tests cover separate transitions. | Simplify temporary-path setup; retain lifecycle branches. |
| `tests/core/test_system_state.py` | KIS readiness requires both worker and auth state. | `test_unused_public_state_helpers_are_removed` asserts deleted names rather than behavior. | **Delete candidate C1**; retain readiness state test. |
| `tests/core/test_trading_config.py` | Market-prefix mapping and JSON event escaping preserve public configuration/web contracts. | Independent small contracts. | Retain. |
| `tests/data/test_data_service_scope.py` | Toss scope filters account data and scope reaches the portfolio worker. | Different filter and orchestration boundaries. | Retain; compare with direct scope-normalization gap. |
| `tests/data/test_gsheet.py` | Worksheet parser preserves cash-only accounts and ignores sheet current-price values. | Small fake worksheet, no duplicate found. | Retain. |
| `tests/data/test_kis_portfolio.py` | KIS portfolio adapter returns an empty standardized source when upstream fetch reports an error. | One fail-safe adapter test. | Retain; add normal/malformed conversion only if U3 gap ranking selects it. |
| `tests/data/test_portfolio.py` | KIS/Toss/GSheet scope selection, cache refresh/failure, source merge, price fallback, and Toss fallback preserve portfolio policy. | Ten tests use repeated source patches but cover different scopes, cache states, and fallback outcomes. | Retain; extract local source payload/patch helpers only if they reduce repetition without hiding policy. |
| `tests/data/test_toss_portfolio.py` | Toss holdings and buying power convert into standardized portfolio data. | One rich response fake checks cross-currency conversion. | Retain; malformed buying-power boundary is a risk-gap candidate. |
| `tests/data/test_weights.py` | Core/satellite grouping, leverage, group valuation, and weight diffs lead to intended allocation/trade quantities. | Cases cover distinct portfolio policy rules. | Retain. |
| `tests/kis/test_broker.py` | KIS/Toss broker choice, REST-disabled fail-closed behavior, order/cancel routing, price/portfolio retrieval, cash semantics, and holdings merge policy. | Several REST-disabled tests share setup but block distinct side effects (orders, cancel, portfolio, prices, worker auth). | Retain behavior tests; consider local disabled-auth helper only. |
| `tests/kis/test_kis_replay.py` | Sanitized websocket fixture records normalize to configured field width. | Single offline replay seam. | Retain; extended parser/error cases are covered in realtime/logging suite. |
| `tests/kis/test_realtime_and_logging.py` | Websocket tick logging, KIS log sanitization, record normalization, schema-drift warning limits, and worker-stop handling avoid sensitive/invalid output. | Parser and logger branches have distinct safety effects. | Retain; U3 may add event payload state/idempotency tests outside this module. |
| `tests/scheduler/test_portfolio_report.py` | Portfolio-report comparison uses configured exchange-rate fallback. | One filesystem/config seam. | Retain. |
| `tests/scheduler/test_scheduler_order.py` | Daily order report runs suite once; disabled periodic rebalancing remains quiet. | Separate scheduling and disabled behavior. | Retain. |
| `tests/strategy/test_raoeo_properties.py` | Cash funding never sells more than holdings; rebalancing emits positive quantities. | Rebalance property test mirrors portions of calculation policy and needs invariant-focused review. | Simplify candidate S1; preserve independent quantity/budget/holding invariants. |
| `tests/strategy/test_report_formatter.py` | Strategy and rebalancing reports show status, orders, funding, and error states. | Each fixture covers a distinct presentation state. | Retain. |
| `tests/strategy/test_strategy_workflows.py` | RAOEO/VA/rebalancing calculate, fund, execute, audit, order, reuse snapshots, and persist strategy history correctly. | Large shared helpers and many patches are orchestration seams; tests generally cover distinct ordering/failure policies. One test only checks that `_get_market_status` is absent. | **Delete candidate C2** for internal-name assertion; retain and later simplify shared setup selectively. |
| `tests/strategy/test_value_averaging.py` | Disabled/empty targets, KRW sales, thresholds, daily cap, history, and sub-share conditions create valid value-averaging orders. | Parameterized boundaries are already compact. | Retain; rank invalid/zero-price and fractional/negative data gaps in U3. |
| `tests/telegram/test_bot.py` | Telegram command confirmation, runtime gates, strategy funding, history validation, portfolio scope, cache refresh, and display privacy behave safely. | Async command flows cover separate user interactions; mocks are appropriate at Telegram boundary. | Retain; no consolidation before a flow-level overlap is shown. |
| `tests/telegram/test_utils.py` | Reply/edit/send wrappers retry, handle missing state, schedule notifications, and avoid sending when unconfigured. | Module reset and fakes isolate async globals. | Retain. |
| `tests/toss/test_api_helpers.py` | Toss account/header requests, token lifecycle, order mapping, cancel/list behavior, rate limiting, HTTP/transport failure handling, and request sanitization remain offline. | `unittest` setup manually removes fixed temporary directories; rate-limit tests cover interval, 429, final HTTP, transport, and sanitization branches. `test_get_holdings_does_not_expose_default_account_resolver` is structural only. | **Delete candidate C3**; simplify temporary paths; retain rate-limit contracts and add only uncovered malformed-header/boundary cases. |
| `tests/toss/test_query_helpers.py` | Query validation/encoding and required response validation for candles, calendar, trades, orders, commissions, and quantities. | Parameterization is already used for validation families. | Retain; add only unrepresented endpoint/error contract selected in U3. |
| `tests/toss/test_toss_replay.py` | Sanitized Toss holdings normal/empty/null responses replay through injected HTTP. | Three distinct response shapes, no generic replay abstraction. | Retain. |

## Approved-For-Review Candidate List

These are the only removal/consolidation candidates identified by U1. They
are **not yet approved for modification**; U2 must use this list as its
boundary.

| ID | Candidate | Unique observable contract? | Proposed action | Representative coverage retained |
| --- | --- | --- | --- | --- |
| C1 | `test_unused_public_state_helpers_are_removed` in `tests/core/test_system_state.py` | No. It asserts absence of historical helper names, not readiness behavior. | **Removed in U2.** | `test_kis_ready_reflects_worker_and_auth_state` remains the state contract. |
| C2 | `test_execution_service_uses_market_utils_status_directly` in `tests/strategy/test_strategy_workflows.py` | No. It asserts absence of `_get_market_status`; weekend/runtime workflow tests exercise market-status behavior. | **Removed in U2.** | `test_run_raoeo_stops_before_market_data_on_weekend` and workflow execution tests retain observable behavior. |
| C3 | `test_get_holdings_does_not_expose_default_account_resolver` in `tests/toss/test_api_helpers.py` | No. It asserts a private helper is not exported. | **Removed in U2.** | Account sequence cache and holdings request/header tests retain supported behavior. |
| S1 | Rebalance property expectation in `tests/strategy/test_raoeo_properties.py` | Partly. Positive quantity is valuable; full expected-order reconstruction mirrored the production formula. | **Simplified in U2** to order invariants. | Positive quantity, sell ≤ holdings, and buy total matches emitted orders. |
| S2 | Fixed temporary directories in `tests/core/test_runtime.py` and `tests/toss/test_api_helpers.py` | Yes, but setup is over-specified. | **Simplified in U2** with per-test `TemporaryDirectory` cleanup while preserving the existing `unittest` style. | Current-format and legacy credential parsing; token issue/renewal behavior. |
| S3 | Repeated KIS-disabled and portfolio-source patch setup | Yes, each protected branch is distinct. | Retained unchanged in U2: no helper reduced setup without obscuring the protected policy branch. | Existing per-entry-point tests; none are deleted solely for sharing setup. |

## Ranked Risk-Gap Map

New tests are additions only after the listed source behavior and existing
tests are read together during U3. A gap means “no direct contract located in
the current suite,” not “production behavior is known faulty.”

| Priority | Risk boundary | Current evidence | Candidate offline regression contract | Likely test location |
| --- | --- | --- | --- | --- |
| P0 | Portfolio scope normalization | `src/data/portfolio_scope.py` had no matching direct test module; scope tests entered later at data service/integration. | **Added in U3:** missing values default to `all`, supported values normalize case/whitespace, and unsupported values fail before a broker fetch. | `tests/data/test_portfolio_scope.py`. |
| P0 | Rebalancing price safety | Property suite asserts positive quantities, while workflows pass orderable cash into calculation. | **Added in U3:** a missing asset price returns no executable orders. | `tests/strategy/test_rebalancing.py`. |
| P0 | KIS malformed event handling | No direct `kis_event_handler` test module; current realtime suite focuses on logs/parser normalization. | **Added in U3:** empty frames and malformed domestic order rows report an error without notification or order-sync side effects. | `tests/kis/test_event_handler.py`. |
| P1 | Toss rate-limit header parsing | **Added:** malformed `Retry-After` uses deterministic fallback backoff; `max_retries=1` makes exactly two attempts and one delay. | Retry parsing and retry boundary remain offline and deterministic. | `tests/toss/test_api_helpers.py`. |
| P1 | Broker error and payload boundaries | **Added:** Toss and KIS reject malformed USD buying-power values; both brokers reject unsupported order types before authentication or order submission. | Invalid broker input fails locally with a clear error and no order side effect. | `tests/toss/test_api_helpers.py`, `tests/kis/test_broker.py`. |
| P2 | Runtime/web concurrent transition edges | **Added:** an `off` command waits for an in-progress `on` command, then stops the fully started runtime. | Shared runtime lock prevents interleaved dependency start/stop. | `tests/core/test_runtime.py`. |
| P2 | Value-averaging numeric boundaries | **Added:** zero and negative input prices create no order; negative prices normalize to zero in retained context. | Non-positive pricing cannot reach order quantity division. | `tests/strategy/test_value_averaging.py`. |

## U1 Completion Evidence

- All 26 discovered `test_*.py` modules are represented in the inventory.
- `tests/architecture/test_boundaries.py` statically checks the target layer
  rules and the KIS vendor boundary at
  `src/infrastructure/kis/kis_api/`. U3 retires the temporary allowance:
  `LEGACY_IMPORT_ALLOWLIST_VERSION = 2` is explicitly empty, and vendor
  imports are checked in a subprocess for application-owned side effects.
- C1–C3 have a named surviving behavior contract; no other deletion candidate
  is proposed.
- Large KIS broker, strategy workflow, portfolio integration, architecture,
  and Telegram tests are explicitly retained pending setup-only review.
- Static safety review found no intended live credential, network, runtime, or
  order path. Runtime verification is deferred to U4.

## U2 Verification

- `venv/bin/pytest tests/core/test_system_state.py tests/core/test_runtime.py
  tests/strategy/test_strategy_workflows.py
  tests/strategy/test_raoeo_properties.py tests/toss/test_api_helpers.py`
  passed: 78 tests.

## Accepted and Resolved Policy Notes

- `rebalancing.calculate_orders()` intentionally returns reportable buy orders
  even when `total_buy_required` exceeds `total_available`. The accepted policy
  is to submit that order and let the broker reject it, with the resulting
  notification left for the user to act on; no calculation or execution cap is
  added.
- KIS order-notification deduplication now suppresses only exact repeated
  in-process events. Its key includes TR ID, order number, symbol, time,
  status, quantity, and price, preserving distinct partial fills. The cache is
  bounded to 1,000 events and intentionally does not survive a restart.

## U3 Verification

- `venv/bin/pytest tests/data/test_portfolio_scope.py
  tests/strategy/test_rebalancing.py tests/kis/test_event_handler.py
  tests/core/test_system_state.py tests/core/test_runtime.py
  tests/strategy/test_strategy_workflows.py
  tests/strategy/test_raoeo_properties.py tests/toss/test_api_helpers.py`
  passed: 88 tests.
- `venv/bin/ruff check tests/data/test_portfolio_scope.py
  tests/strategy/test_rebalancing.py tests/kis/test_event_handler.py` passed.

## U4 Verification

- `venv/bin/pytest tests` passed: 263 tests after the duplicate-event coverage
  was added.
- `docker compose build test && docker compose run --rm test` passed: 261
  tests on Python 3.11. The later duplicate-event verification passed: 263
  tests. The initial Docker run collected 254 tests because it
  used a pre-U3 image; rebuilding the test image was required before accepting
  the container result.

## P1/P2 Follow-up Verification

- `venv/bin/pytest tests/toss/test_api_helpers.py tests/kis/test_broker.py
  tests/core/test_runtime.py tests/strategy/test_value_averaging.py` passed:
  106 tests.
- `venv/bin/ruff check src/infrastructure/toss/toss_broker.py src/broker/kis_broker.py
  tests/toss/test_api_helpers.py tests/kis/test_broker.py
  tests/core/test_runtime.py tests/strategy/test_value_averaging.py` passed.
- `venv/bin/pytest tests` passed: 272 tests.
- `docker compose build test && docker compose run --rm test` passed: 272
  tests on Python 3.11.

## Layered Architecture Follow-up Verification

- `venv/bin/pytest tests` passed: 303 tests after the interface/application
  migration slices.
- `venv/bin/ruff check src tests` passed.
- Architecture checks now import scheduler and Telegram adapters from
  `src/interfaces/` and retain subprocess import-safety coverage.
- `docker compose run --rm test` passed: 303 tests on Python 3.11 after the
  current interface/application migration slices.
