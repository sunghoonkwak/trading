# Toss Invest Helpers (`src/toss/`)

This package contains small command-line and importable helpers for the Toss
Invest Open API.

## Reference

Before changing Toss request code, check the OpenAPI schema at
`docs/reference/toss-openapi-v1.1.1.json`.

Useful lookup patterns:

```bash
rg -n '"/api/v1/orders|operationId|cancelOrder|modifyOrder' docs/reference/toss-openapi-v1.1.1.json
```

Confirm these details from the schema:

- endpoint path and HTTP method
- request `Content-Type` and body shape
- `X-Tossinvest-Account` header requirements
- response field names such as `orderId`, `orders`, and `nextCursor`

## Runtime Notes

- Load tokens through `toss.get_prices.load_access_token()`.
- Resolve default account sequence through
  `toss.get_holdings._get_default_account_seq(access_token)`.
- Keep order-changing diagnostics (`create_order`, `modify_order`,
  `cancel_order`) behind explicit user approval.
- Toss API calls currently routed through the shared rate-limit manager:
  `auth`, `get_accounts`, `get_holdings`, `get_buying_power`, `get_prices`,
  `get_orders`, `get_order`, `create_order`, `modify_order`, and
  `cancel_order`.
- TODO: migrate the remaining lower-priority helpers to the shared manager:
  `get_candles`, `get_commissions`, `get_exchange_rate`,
  `get_kr_market_calendar`, `get_orderbook`, `get_price_limit`,
  `get_sellable_quantity`, `get_trades`, and `get_us_market_calendar`.
- The shared Toss request helper logs requests and responses at INFO while the
  integration is new. After the runtime is stable, lower these logs to DEBUG in
  `toss.client`.
