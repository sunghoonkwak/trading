# KIS portfolio source adapter

`kis_source.py` isolates the portfolio merge adapter from the temporary
`broker.kis_portfolio` compatibility surface. It preserves the normalized KIS
source and metadata contract while callers migrate to the infrastructure KIS
adapter.
