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
