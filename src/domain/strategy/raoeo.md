# RAOEO strategy

`raoeo.py` is a pure calculation module. Given configuration, holdings, prices,
and history, it selects the configured phase and returns broker-independent
`StrategyOrder` values plus metadata. It makes no API calls or state changes.

Current prices prefer the supplied market snapshot and fall back to a holding's
recorded price. Buy pricing applies the established safety cap; normal and
average orders preserve budget carryover, while filling orders preserve their
target-quantity rule. Cash-funding orders are produced only by the explicit
manual approval path.
