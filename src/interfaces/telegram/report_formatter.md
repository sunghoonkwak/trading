# Telegram Strategy Report Formatter (`src/interfaces/telegram/report_formatter.py`)

This interface formatter turns structured strategy result data into Telegram
HTML. It owns presentation only and does not call brokers or application use
cases.

- `format_strategy_report()` renders RAOEO and Value Averaging status, market
  state, orders, execution results, and optional RAOEO cash-funding context.
- `format_rebalancing_report()` renders rebalancing state, allocation details,
  and execution results.
- `StrategyStatus` values are mapped to user-facing emoji and messages at this
  transport boundary.

```python
from interfaces.telegram.report_formatter import format_strategy_report

report_html = format_strategy_report(raoeo_result, va_result)
```
