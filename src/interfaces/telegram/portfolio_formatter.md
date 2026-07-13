# Telegram Portfolio Formatter (`src/interfaces/telegram/portfolio_formatter.py`)

`format_portfolio_summary()` converts the normalized portfolio result and an
injected Fear & Greed reader into Telegram HTML. It presents totals, cash,
US/Korean asset statistics, exchange rate, and a ticker-selection prompt; an
application error becomes a safe Telegram error message.
