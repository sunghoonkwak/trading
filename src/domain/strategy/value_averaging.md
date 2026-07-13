# Value averaging strategy

`value_averaging.py` calculates broker-independent orders that move each target
toward its accumulated daily value. It takes configuration, holdings, current
prices, history, and a US trading date, then returns orders and history context.

Price resolution prefers the supplied snapshot and then the holding fallback.
The module is pure and does not read history or call a broker itself.
