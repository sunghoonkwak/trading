# Value Averaging Strategy (`src/strategy/value_averaging.py`)

이 모듈은 Value Averaging (VA) 전략의 순수 계산 로직을 담당합니다. 목표 자산 가치에 도달하기 위한 매수/매도 주문량을 계산합니다.

## Core Logic (핵심 로직)

1. **Target Value Calculation (목표 가치 계산)**:
   - `day_count` (일차) x `daily_budget` (일 목표액)으로 누적 목표 가치를 산출합니다.

2. **Divergence Check (이격도 확인)**:
   - 현재 자산 가치(`current_value`)와 목표 가치(`target_value`)의 차이를 계산하여 주문 필요 여부를 결정합니다.
   - 주문 수량 계산에 쓰는 현재가는 `utils.price_utils.resolve_current_price`를 통해
     `current_prices` 우선, 보유 잔고의 `cur_price` fallback 순서로 해석합니다.

3. **History Integration (히스토리 통합)**:
   - `day_count`는 `strategy_history.json`에서 로드된 이전 이력(`targets_context`)을 기반으로 계산됩니다.

## Key Functions (주요 함수)

### `calculate_orders`
VA 공식에 따라 필요한 주문을 계산합니다.

- **입력 (Input)**:
  - `targets_config` (Dict): 종목별 VA 설정 (daily_budget, target 등)
  - `portfolio` (Dict): 현재 보유 잔고 (평가액, 수량)
  - `current_prices` (Dict): 현재 시장가. 값이 없거나 0 이하이면 해당
    보유 잔고의 `cur_price`를 fallback으로 사용합니다.
  - `history_data` (List[Dict]): 로드된 히스토리 데이터 (day_count 추적용)
  - `today_date` (str): 오늘 날짜 (YYYY-MM-DD)
- **출력 (Output)**: `Tuple[List[StrategyOrder], Dict]`
  - `orders`: 생성된 주문 리스트 (LIMIT/LOC 등)
  - `context_map`: 히스토리에 저장할 컨텍스트 (day_count 업데이트용)

## Configuration (`strategy_config.json`)

```json
{
  "value_averaging": {
    "enabled": true,
    "targets": {
      "QLD": {
        "enabled": true,
        "target": 5000,
        "daily_budget": 100,
        "threshold_rate": 0.15
      }
    }
  }
}
```

## Usage Example (사용 예시)

```python
from strategy import value_averaging

orders, context = value_averaging.calculate_orders(
    targets_config={...},
    portfolio={...},
    current_prices={...},
    history_data=[...],
    today_date="2026-02-18"
)
```
