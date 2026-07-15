# Strategy execution lifecycle

This module owns the common session state for a configured strategy run:
date, market status, base report, history service, and order report service.
It also filters enabled target configurations and looks up one date in the
list-shaped strategy history document. Strategy-specific calculations and order
policies remain in `strategy_execution.py`.
