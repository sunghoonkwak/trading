# Order Report Service (`src/application/order_report_service.py`)

This application service executes domain `StrategyOrder` values through an
injected order port and returns channel-neutral result dictionaries. It never
formats or sends Telegram, web, or scheduler output.

## Services

- `OrderManagementService` exposes injected open-order synchronization, reads,
  and explicit cancel/correction actions for transport adapters.
- `OrderReportService.execute()` assigns a correlation ID when absent, executes
  one order, and optionally reconciles an ambiguous result without resubmitting.
- `execute_many()` preserves optional sell-first ordering and waits only when
  both sell and buy orders exist.
- `retry_failed()` returns execution results plus succeeded and pending orders.
