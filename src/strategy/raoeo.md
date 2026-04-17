# RAOEO Strategy (`src/strategy/raoeo.py`)

이 모듈은 RAOEO (Reverse Accumulating Order Execution) 전략의 순수 계산 로직을 담당합니다. 마켓 상태나 실행 여부와 관계없이 설정과 현재가에 기반한 주문을 생성합니다.

# Core Logic (핵심 로직)

1. **Pure Function (순수 함수)**:
   - 외부 API 호출이나 상태 변경 없이, 입력값(`config`, `portfolio`, `price`)만으로 주문을 계산합니다.

2. **Order Calculation (주문 계산)**:
   - **4단계 Phase (매수/매도 정책)**:
     - **Phase 0 (10% 미만)**: 매수(10% 채우기 포함) 진행, 목표 수익률의 2배를 기준으로 도출된 목표 매도가로 **매도 주문 실행**. 매수가는 `목표 매도가 - 0.01불`
     - **Phase 1 (10%~20% 미만)**: 일반 매수 진행, 목표 수익률의 2배를 기준으로 도출된 목표 매도가로 **매도 주문 실행**. 매수가는 `목표 매도가 - 0.01불`
     - **Phase 2 (20%~50% 미만)**: 일반 매수 진행, 목표 수익 달성 시 **전량 매도**. 매수가는 `목표 매도가(1배수익) - 0.01불`
     - **Phase 3 (50% 이상)**: 공격적 매수(평단/상단) 진행, 목표 수익 달성 시 **전량 매도**. 상단 매수가는 `목표 매도가(1배수익) - 0.01불`
   - **평단가 부재 시 대응**: 전량 매도 후 등 평단가(`avg_price`)를 알 수 없는 경우, **현재가(`cur_price`)**를 기준으로 매수 가격과 수량을 계산합니다.
   - **Phase 0 채우기**: 보유 금액이 Seed의 10% 미만일 때, 현재가(또는 평단가)의 95% 가격으로 10% 수준까지 한꺼번에 채우는 주문을 생성합니다.

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
