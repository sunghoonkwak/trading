# Rebalancing strategy

`rebalancing.py` is a pure calculation module for returning holdings to target
weights. It returns proposed broker-independent orders and metadata from the
configured assets, holdings, current prices, reserved cash, and orderable USD.

Price resolution prefers the supplied snapshot and then the holding fallback.
The caller supplies orderable USD; the domain module never queries KIS.
