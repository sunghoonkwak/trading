# Value Averaging Strategy (`src/strategy/value_averaging.py`)

**Value Averaging (VA)** 전략의 순수 계산 로직을 구현한 모듈입니다.
현재 자산 가치와 목표 가치 간의 차액(괴리율)을 계산하여, 목표보다 부족하면 매수하고 초과하면 매도하는 주문을 생성합니다.

# Core Logic (핵심 로직)

1. **목표 가치 계산**: `일일 예산(Budget) × 경과 일수(Day Count)`
2. **현재 가치 평가**: 보유 수량 × 현재가 (또는 평단가)
3. **괴리율(Divergence) 계산**: `(목표 가치 - 현재 가치) / 목표 가치`
4. **주문 결정**:
   - **매수**: 괴리율 ≥ 임계값(`threshold_rate`)이고 자산이 부족할 때.
   - **매도**: 자산이 목표를 초과할 때 (시장가 매도).
   - **건너뜀(Skip)**: 괴리율이 임계값 미만일 때.

# Key Functions (주요 함수)

## `calculate_orders`
VA 전략에 따른 매수/매도 주문을 계산합니다.

- **입력 (Input)**:
  - `targets_config` (dict): 종목별 설정 (예산, 목표액 등).
  - `portfolio` (dict): 현재 잔고 정보.
  - `current_prices` (dict): 실시간 현재가.
  - `history_data` (list): 과거 실행 이력 (Day Count 계산용).
  - `today_date` (str): 오늘 날짜 (YYYY-MM-DD).
- **출력 (Output)**:
  - `orders` (List[StrategyOrder]): 실행할 주문 목록.
  - `context` (Dict): 이력 저장을 위한 계산 결과 (괴리율, 목표액 등).

# Configuration (`strategy_config.json`)

```json
{
  "value_averaging": {
    "targets": {
      "QLD": {
        "daily_budget": 100, // 일일 적립 목표액 ($)
        "target": 10000,     // 최종 목표 금액 ($)
        "threshold_rate": 0.15, // 매매 실행 임계값 (15%)
        "enabled": true
      }
    }
  }
}
```

# Usage Example (사용 예시)

```python
from strategy.value_averaging import calculate_orders

# 데이터 준비
config = {"QLD": {"daily_budget": 100}}
history = [{"date": "2026-02-13", "targets": {"QLD": {"day_count": 5}}}]

# 계산
orders, ctx = calculate_orders(config, portfolio, prices, history, "2026-02-14")
```
