# Scheduled portfolio report interface adapter

`portfolio_runner.py` creates the daily portfolio history and Telegram-facing
report from an injected `PortfolioReader`. Tuesday through Saturday collect
and report fresh data; Monday reuses Friday's saved report data; Sunday skips
the job.

History stays under the composition-provided `portfolio_history` directory.
Comparison output covers one day, week, and month, with KRW and USD totals and
the largest movers. Data timeouts remain visible through the configured
notification path.
