# RAOEO Strategy (`src/strategy/raoeo.py`)

이 모듈은 RAOEO (Reverse Accumulating Order Execution) 전략의 순수 계산 로직을 담당합니다. 마켓 상태나 실행 여부와 관계없이 설정과 현재가에 기반한 주문을 생성합니다.

# Core Logic (핵심 로직)

1. **Pure Function (순수 함수)**:
   - 외부 API 호출이나 상태 변경 없이, 입력값(`config`, `portfolio`, `price`)만으로 주문을 계산합니다.

2. **Order Calculation (주문 계산)**:
   - 목표 수익률(`sell_profit`) 달성 시 매도 주문 생성
   - 매수 조건 충족 시 분할 매수 주문 생성

3. **Buy Price Cap (매수 가격 상한)**:
   - KIS는 현재가의 30% 초과 매수 주문을 거절하므로, 안전 마진을 두고 **25%** 캡을 적용합니다.
   - `_cap_buy_price()`: 계산된 매수 가격이 `cur_price * 1.25`를 초과하면 캡으로 제한합니다.
   - 상수 `MAX_BUY_PRICE_RATIO = 1.25`로 관리됩니다.

# Key Functions (주요 함수)

## `calculate_orders`
설정과 시장 데이터를 기반으로 매수/매도 주문을 계산합니다.

- **입력 (Input)**:
  - `targets_config` (Dict): 종목별 설정 (seed, duration 등)
  - `portfolio` (Dict): 현재 보유 잔고 (qty, avg_price 등)
  - `current_prices` (Dict): 현재 시장가
- **출력 (Output)**: `Tuple[List[StrategyOrder], Dict]` (주문 목록, 메타 정보)

# Configuration (`strategy_config.json`)

```json
{
  "raoeo": {
    "enabled": true,
    "targets": {
      "SOXL": {
        "enabled": true,
        "seed": 20000,
        "exchange": "AMS",
        "duration": 40,
        "sell_profit": 0.1
      }
    }
  }
}
```

# Usage Example (사용 예시)

```python
from strategy import raoeo

# 주문 계산 (실행 X)
orders, info = raoeo.calculate_orders(
    targets_config={...},
    portfolio={...},
    current_prices={"SOXL": 35.5}
)
```
