# Strategy execution recovery service

`execution_recovery_service.py` owns the history-to-retry policy shared by
RAOEO, Value Averaging, and rebalancing. It restores completed and pending
orders, detects ambiguous broker outcomes, and marks reports as non-retryable
until an operator reconciles them. It does not read files or submit orders.
