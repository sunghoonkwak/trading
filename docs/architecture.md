# Layered Architecture

The production dependency direction is:

```text
interfaces -> application -> domain / application.ports <- infrastructure
                         ^
                    src/main.py
```

`src/main.py` is the production composition root. It wires configuration,
broker, portfolio, notification, event, and transport collaborators without
allowing an interface or application module to construct those adapters.

## Package ownership

| Package | Owns |
| --- | --- |
| `interfaces/` | Web, Telegram, and scheduler transport behavior. |
| `application/` | Portfolio, strategy execution, order reporting, and ports. |
| `domain/` | Strategy rules, portfolio transformations, and value types. |
| `infrastructure/` | KIS, Toss, file, cache, and external-service adapters. |
| `infrastructure/kis/kis_api/` | The isolated KIS vendor distribution. |

`core/` contains runtime technical primitives only. `utils/` remains limited
to dependency-free helpers.

## Compatibility register

Compatibility modules are retained only while an identified consumer remains.
Production code must not introduce new imports from them.

| Surface | Current consumers | Removal condition |
| --- | --- | --- |
| `strategy/base.py`, `strategy/constants.py`, strategy rule wrappers | Tests and external script compatibility | Tests and scripts import `domain.strategy` directly. |
| `data/data_service.py` | `main.py`, legacy data tests | Move weight-diff orchestration to an application use case. |
| `data/portfolio_scope.py` | Portfolio-scope tests | Migrate tests to `domain.portfolio.scope`. |
| `data/portfolio_processing.py` | Broker compatibility tests | Migrate tests to `domain.portfolio.processing`. |
| `data/portfolio_integration.py` | Documentation and historical imports | Remove after documentation and external consumers move. |
| `toss/` | Tests and backtest/script compatibility | Migrate consumers to `infrastructure.toss`. |
| `broker/kis_*` forwarding modules | `main.py`, KIS tests, worker compatibility | Compose direct infrastructure adapters and migrate callers. |

The removed `strategy.execution_service`, `core.web_server`, and
`telegram_bot` surfaces have zero production, test, script, and documentation
consumers.
