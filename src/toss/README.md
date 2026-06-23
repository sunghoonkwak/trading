# Toss Invest Helpers (`src/toss/`)

이 패키지는 Toss Invest Open API를 호출하는 작은 CLI/helper 함수들을
담고 있습니다.

## Reference

Toss 요청 코드를 변경하기 전에는 먼저 체크인된 OpenAPI schema
`docs/reference/toss-openapi-v1.1.1.json`를 확인합니다.

자주 쓰는 검색 패턴:

```bash
rg -n '"/api/v1/orders|operationId|cancelOrder|modifyOrder' docs/reference/toss-openapi-v1.1.1.json
```

schema에서 다음 항목을 확인합니다.

- endpoint path와 HTTP method
- 요청 `Content-Type`과 body 형태
- `X-Tossinvest-Account` header 필요 여부
- `orderId`, `orders`, `nextCursor` 같은 응답 field 이름

## Runtime Notes

- 토큰은 `toss.auth.load_access_token()`을 통해 로드합니다. 이 함수는
  저장된 토큰의 `expires_at`을 확인하고, 만료된 경우 다음 API 요청 전에 새
  토큰을 발급해 반환합니다.
- 기본 계좌 sequence는
  `toss.account_cache.get_default_account_seq(access_token)`로 확인합니다.
  이 값은 같은 프로세스 안에서 `access_token`과 Toss base URL별로 캐시되어
  같은 토큰으로 반복 API 호출 시 `/api/v1/accounts`를 다시 조회하지 않습니다.
- 주문 상태를 바꾸는 진단(`create_order`, `modify_order`, `cancel_order`)은
  사용자의 명시적인 요청이 있을 때만 실행합니다.
- 현재 shared rate-limit manager를 거치는 Toss API 호출:
  `auth`, `get_accounts`, `get_holdings`, `get_buying_power`, `get_prices`,
  `get_orders`, `get_order`, `create_order`, `modify_order`,
  `cancel_order`, `get_candles`, `get_commissions`, `get_exchange_rate`,
  `get_kr_market_calendar`, `get_orderbook`, `get_price_limit`,
  `get_sellable_quantity`, `get_trades`, `get_us_market_calendar`.
- shared manager는 그룹별 Toss TPS 제한과 별도로, 연속 Toss API 요청 사이에
  전역 최소 1초 간격을 둡니다. 전략 실행에서 주문 여러 개가 한 번에 발생해도
  Toss로 나가는 shared helper 요청은 이 간격을 지켜 직렬화됩니다.
- `toss.client.request_json()`은 최종 Toss API query 실패를 RuntimeError로
  올리기 전에 Telegram 알림을 전송합니다. 429 재시도 중간 실패는 알림을
  보내지 않고, 재시도 후에도 실패한 경우에만 알림을 보냅니다.
- shared Toss request helper는 요청/응답 덤프를 DEBUG 로그로 남깁니다.
