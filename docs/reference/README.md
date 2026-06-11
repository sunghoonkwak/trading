# API References

This directory stores API reference material that is useful during local
development.

## Toss Invest Open API

- `toss-openapi-v1.1.1.json`: Toss Invest OpenAPI 3.1 schema.
- Use it before editing `src/toss/` helpers or app-owned Toss integrations.
- Confirm endpoint path, HTTP method, request `Content-Type`, required headers,
  and response fields from the schema instead of guessing from previous code.

The checked-in schema uses example values only. Do not add runtime credentials,
tokens, account numbers, or live payload dumps to this directory.
