# Strategy execution lifecycle

This module owns the common session state for a configured strategy run:
date, market status, base report, history service, and order report service.
It also filters enabled target configurations and looks up one date in the
list-shaped strategy history document. Targets support legacy boolean
`enabled` values and an `enabled` object with `buy` and `sell` booleans. A
target remains active while either order side is enabled; it is excluded only
when both sides are disabled. Strategy-specific calculations and order policies
remain in `strategy_execution.py`.
