# Toss Broker Facade (`src/broker/toss_broker.py`)

전략 실행에서 Toss Invest API를 사용할 때 필요한 앱 소유 facade입니다.

## Responsibilities

- Toss `buying-power`의 `cashBuyingPower`를 USD 매수 가능 금액으로
  반환합니다.
- `StrategyOrder`를 Toss 주문 생성 API 인자로 변환합니다.
- 전략 주문 의도 `LOC`는 Toss `LIMIT` + `timeInForce=CLS`로
  변환합니다.

## Boundaries

토큰 로드, 기본 계좌 선택, HTTP 호출은 기존 `src/toss/` helper를
사용합니다. 실제 계좌에 영향을 주는 주문 생성은
`strategy_broker.place_order()`를 통해 선택된 경우에만 호출됩니다.
