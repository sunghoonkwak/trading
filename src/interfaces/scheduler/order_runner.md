# Scheduled order interface adapter

`order_runner.py` invokes the injected strategy-run use case and formats its
structured results for Telegram notification. Daily RAOEO and value-averaging
runs share the application suite result.

Periodic rebalancing only runs during 09:40–15:40 US/Eastern. Its first call
for a trading date can notify an already-complete result; later calls notify
new execution, partial, or error results. A disabled strategy exits quietly.
