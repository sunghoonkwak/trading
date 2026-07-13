# Toss Portfolio Adapter

`infrastructure.toss.portfolio` reads Toss holdings and buying power into the
normalized portfolio-source format.

## Responsibilities

- Reads the `토스` account with the default portfolio account sequence of `1`.
- Converts holdings into normalized holdings and asset metadata.
- Converts KRW and USD `cashBuyingPower` values into cash holdings.

## Boundaries

`infrastructure.portfolio.integration` loads this adapter when merging source
data. The API paths, response fields, token access, and portfolio account
default remain contained in the Toss infrastructure adapter.
