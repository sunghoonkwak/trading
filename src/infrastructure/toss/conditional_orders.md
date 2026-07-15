# Toss Conditional Orders (`src/infrastructure/toss/conditional_orders.py`)

The module exposes explicit helpers to create, list, inspect, modify, and
cancel Toss conditional orders. It is intentionally not connected to strategy
execution. Callers must opt in to every state-changing request and retain the
new identifier returned by a successful modification.
