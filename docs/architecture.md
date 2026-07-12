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
| `data/data_service.py` | `main.py` weight-diff wiring and legacy data tests | Replace the remaining weight-diff collaborator before removal. |
| `toss/` | `main.py` token startup plus Toss tests/backtest compatibility | Migrate callers to `infrastructure.toss`. |
| `broker/kis_*` forwarding modules | `main.py`, KIS tests, worker compatibility | Compose direct infrastructure adapters and migrate callers. |

The removed `strategy.execution_service`, `core.web_server`, `telegram_bot`,
and data portfolio forwarding surfaces have zero production, test, script,
and documentation consumers.

`interfaces.web.create_web_app()` is a factory: each application owns its
dependencies, connection manager, event-loop callback, and lifespan. The
production composition root passes that exact application instance to
`start_web_server()`; no module-level web application or dependency registry is
used.

Telegram portfolio and rebalancing handlers are registered with factory-owned
application collaborators. Scheduler production composition uses
`SchedulerRunner` and `SchedulerOrderRunner`; its legacy module functions stay
only while scheduler tests and external automation still consume them.
