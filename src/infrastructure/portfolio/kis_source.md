# KIS Portfolio Source Adapter

`kis_source.py` is the infrastructure-owned KIS portfolio source adapter. It
reads KIS REST balances, normalizes holdings and orderable cash, and preserves
the existing fail-safe empty-source result when KIS reports an error.

Local KIS portfolio alerts are supplied by the composition root through
`configure_alert_publisher()`. Publication is best-effort and cannot change a
portfolio retrieval result.

The composition root also supplies the KIS REST and domestic-account feature
flags through `configure_feature_flags()`. Without a REST flag collaborator,
the adapter returns the existing disabled empty result before authentication or
an account API call.

## Worker boundary

The composition root supplies `SerializedKisOperations` through
`configure_serialized_operations()`. Every enabled portfolio read is submitted
to the KIS worker with an isolated response queue, request ID, and correlation
ID. A timeout cancels waiting and safely discards a late read response; a
currently executing vendor call cannot be interrupted, so no partial response
is returned. The adapter turns any failed operation into the established empty
source plus error metadata.
