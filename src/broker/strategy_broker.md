# Strategy Broker Selector (`src/broker/strategy_broker.py`)

전략 실행 계좌를 `strategy_config.json`의 `strategy_broker` 값으로
선택하는 얇은 broker facade입니다.

## Configuration

```json
{
  "strategy_broker": "kis"
}
```

- 허용값: `"kis"`, `"toss"`
- 기본값: `"kis"`

## Responsibilities

- 전략 포트폴리오 scope가 사용할 계좌명을 반환합니다.
- 매수 가능 USD 조회를 선택된 broker 구현으로 위임합니다.
- `StrategyOrder` 주문 접수를 선택된 broker 구현으로 위임합니다.

KIS/Toss API 세부 필드명과 주문 변환은 각각 `kis_broker.py`와
`toss_broker.py`가 담당합니다.
