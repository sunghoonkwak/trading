# Runtime lifecycle contract

`runtime_service.py` is the application-facing contract between runtime
controls and `main.TradingSystem`. `RuntimeController` supplies serialized
start, stop, and status operations from the composition root.

`RuntimeCommandResult` carries success, user-facing text, an optional failed
component, and whether the requested lifecycle state was already active.
Interfaces must return a failed result when no controller is available; they
must not raise or start runtime components directly.
