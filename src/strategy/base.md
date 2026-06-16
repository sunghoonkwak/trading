# Strategy Base (`src/strategy/base.py`)

전략 모듈 간에 공유되는 **기본 데이터 구조**를 정의하는 모듈입니다.
특히 주문 객체(`StrategyOrder`)와 실행 상태(`StrategyStatus`)의 표준 포맷을 제공하여 전략 계산 로직과 실행 로직 간의 결합도를 낮춥니다.

## Core Logic (핵심 로직)

이 모듈은 로직보다는 **데이터 정의(Data Definition)**에 초점을 맞춥니다.
`dataclass`와 `Enum`을 사용하여 타입 안전성을 보장하고, 코드 가독성을 높입니다.

## Key Functions (주요 클래스/함수)

### `OrderSide` (Enum)
주문의 방향(매수/매도/보유)을 정의합니다.
- `BUY`: 매수
- `SELL`: 매도
- `HOLD`: 관망

### `StrategyStatus` (Enum)
전략 실행 결과를 통합 관리하기 위한 상태값입니다.
- `EXECUTED`: 모든 주문 성공
- `PARTIAL`: 일부 주문 실패 (재실행 필요)
- `SKIPPED`: 조건 미달로 주문 없음
- `HOLIDAY`: 휴장일로 실행 안 함
- `NON_MARKET_TIME`: 장 운영 시간이 아님
- `DISABLED`: 전략 비활성화 상태
- `ERROR`: 실행 중 오류 발생
- `ALREADY_DONE`: 이미 실행 완료 (중복 실행 방지용)

### `StrategyOrder` (dataclass)
전략 계산 결과로 생성되는 단일 주문 정보를 담습니다.

- **속성 (Attributes)**:
  - `symbol` (str): 종목 코드 (예: "SOXL")
  - `side` (OrderSide): 주문 방향
  - `quantity` (int): 주문 수량
  - `price` (float): 주문 가격 (0이면 시장가)
  - `order_type` (str): 브로커 독립 주문 의도 (`LIMIT`, `LOC` 등)
  - `reason` (str): 주문 사유 (로그/디버깅용)

### `__str__`
주문 객체를 문자열로 표현할 때 사용되는 포맷팅 메서드입니다.
- 예: `[SOXL] BUY 10 ($35.50) - Phase 1 Buy`

## Configuration (None)
설정 파일이 필요하지 않습니다.

## Usage Example (사용 예시)

```python
from strategy.base import StrategyOrder, OrderSide, StrategyStatus

# 상태값 사용
status = StrategyStatus.EXECUTED

# 주문 생성
order = StrategyOrder(
    symbol="SOXL",
    side=OrderSide.BUY,
    quantity=10,
    price=35.5,
    reason="Phase 1 Buy"
)
```
