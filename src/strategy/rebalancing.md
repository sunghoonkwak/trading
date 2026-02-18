# Rebalancing Strategy (`src/strategy/rebalancing.py`)

이 모듈은 자산 배분 비중을 일정하게 유지하기 위한 리밸런싱 전략의 순수 계산 로직을 담당합니다. 총 자산을 목표 비율에 맞춰 재분배합니다.

# Core Logic (핵심 로직)

1. **Asset Allocation (자산 배분)**:
   - 총 자산(현금 + 주식)을 계산하고, 설정된 `target_weight`에 따라 각 자산의 목표 금액을 산출합니다.

2. **Order Generation (주문 생성)**:
   - 현재 가치와 목표 가치의 차이를 계산하여 매수/매도 주문을 생성합니다.
   - `reserved_cash`를 고려하여 RAOEO 등 타 전략에 필요한 예산을 제외하고 리밸런싱 자원을 할당합니다.

# Key Functions (주요 함수)

## `calculate_orders`
리밸런싱 공식에 따라 주문을 계산합니다.

- **입력 (Input)**:
  - `config` (Dict): 리밸런싱 설정 (`assets`, `seed`, `rebalance_threshold`)
  - `portfolio` (Dict): 자산별 현재 잔고
  - `current_prices` (Dict): 자산별 현재 가격
  - `reserved_cash` (float): 타 전략을 위해 예약된 현금 (사용 불가)
- **출력 (Output)**: `Tuple[List[StrategyOrder], Dict]`
  - `orders`: 실행할 매수/매도 주문 리스트
  - `info`: 자산 현황, 스케일링 팩터, 비중 차이 등의 메타 정보

# Configuration (`strategy_config.json`)

```json
{
  "rebalancing": {
    "enabled": true,
    "seed": 10000,
    "assets": [
      { "ticker": "TQQQ", "target_weight": 0.5 },
      { "ticker": "SCHD", "target_weight": 0.5 }
    ],
    "rebalance_threshold": 0.05
  }
}
```

# Usage Example (사용 예시)

```python
from strategy import rebalancing

orders, info = rebalancing.calculate_orders(
    config={...},
    portfolio={...},
    current_prices={"TQQQ": 50.0, "SCHD": 30.0},
    reserved_cash=500.0
)
```
