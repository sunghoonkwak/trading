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
| `application/` | Portfolio, strategy execution, account selection, order reporting, and ports. |
| `domain/` | Strategy rules, portfolio transformations, and value types. |
| `infrastructure/` | KIS, Toss, file, cache, and external-service adapters. |
| `infrastructure/kis/kis_api/` | The isolated KIS vendor distribution. |

`core/` contains runtime technical primitives only. `utils/` remains limited
to dependency-free helpers.

## Compatibility register

No compatibility module remains. The removed `broker.market_data`,
`broker.strategy_broker`, `broker.kis_broker`, `broker.toss_broker`,
`broker.toss_portfolio`, `data.data_service`, `strategy.execution_service`,
`core.runtime_control`, `core.web_server`,
`scheduler` forwarding modules, `telegram_bot`, `toss`, and data portfolio
forwarding surfaces (including `data.gsheet` and its legacy integration
sidecar) have zero production, test, script, and documentation consumers. The
retired `strategy.report_formatter` sidecar now documents the Telegram
formatter at its interface destination.

The retired `data.config_manager` and `data.calculate_weights` modules now
live at `infrastructure.config` and `domain.portfolio.weights` respectively.

`interfaces.web.create_web_app()` is a factory: each application owns its
dependencies, connection manager, event-loop callback, and lifespan. The
production composition root passes that exact application instance to
`start_web_server()`; no module-level web application or dependency registry is
used.

Telegram portfolio, memo, rebalancing, and runtime-control handlers are
registered with factory-owned application collaborators. Scheduler production
composition uses `SchedulerRunner`, `SchedulerOrderRunner`, and
`SchedulerPortfolioRunner`; no scheduler module-global collaborator remains.
