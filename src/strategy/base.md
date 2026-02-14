# Strategy Base (`src/strategy/base.py`)

전략 모듈 간에 공유되는 **기본 데이터 구조**를 정의하는 모듈입니다.
특히 주문 객체(`StrategyOrder`)의 표준 포맷을 제공하여 전략 계산 로직과 실행 로직 간의 결합도를 낮춥니다.

# Core Logic (핵심 로직)

이 모듈은 로직보다는 **데이터 정의(Data Definition)**에 초점을 맞춥니다.
`dataclass`와 `Enum`을 사용하여 타입 안전성을 보장하고, 코드 가독성을 높입니다.

# Key Functions (주요 클래스/함수)

## `OrderSide` (Enum)
주문의 방향(매수/매도/보유)을 정의합니다.
- `BUY`: 매수
- `SELL`: 매도
- `HOLD`: 관망

## `StrategyOrder` (dataclass)
전략 계산 결과로 생성되는 단일 주문 정보를 담습니다.

- **속성 (Attributes)**:
  - `symbol` (str): 종목 코드 (예: "SOXL")
  - `side` (OrderSide): 주문 방향
  - `quantity` (int): 주문 수량
  - `price` (float): 주문 가격 (0이면 시장가)
  - `order_type` (str): 주문 유형 코드 ("34": LOC, "00": 지정가 등)
  - `reason` (str): 주문 사유 (로그/디버깅용)

## `__str__`
주문 객체를 문자열로 표현할 때 사용되는 포맷팅 메서드입니다.
- 예: `[SOXL] BUY 10 ($35.50) - Phase 1 Buy`

# Configuration (None)
설정 파일이 필요하지 않습니다.

# Usage Example (사용 예시)

```python
from strategy.base import StrategyOrder, OrderSide

# 주문 생성
order = StrategyOrder(
    symbol="SOXL",
    side=OrderSide.BUY,
    quantity=10,
    price=35.5,
    reason="Phase 1 Buy"
)

print(order)
# 출력: [SOXL] BUY 10 ($35.50) - Phase 1 Buy
```
