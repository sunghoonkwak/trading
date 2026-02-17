# Rebalancing Strategy (`src/strategy/rebalancing.py`)

고정 비중 리밸런싱 전략을 구현하는 모듈입니다. 설정된 Seed 금액과 현재 보유 자산(Stock + Cash)을 기준으로 각 자산의 목표 비중을 유지하도록 매수/매도 주문을 계산합니다.

# Core Logic (핵심 로직)

1. **목표가 설정**:
   - 현재 총 보유 금액(Stock + Cash)과 설정된 `seed` 금액 중 작은 값을 `target_base`로 잡습니다.
   - `target_base`에 각 자산의 `target_weight`를 곱하여 공평한 목표 보유 금액을 산정합니다.
   - **RAOEO 예산 예약**: 가용 현금에서 RAOEO 일일 버짓 합계를 차감하여, 리밸런싱이 RAOEO 매수에 필요한 현금을 사용하지 않도록 보호합니다.
2. **트리거 체크**: 다음 두 조건 중 하나라도 충족되면 리밸런싱을 수행합니다.
   - **조건 1**: 가용 현금으로 비중이 낮은(underweight) 종목을 1주 이상 매수 가능한 경우
   - **조건 2**: 두 종목 간 현재 비중 차이가 `rebalance_threshold`를 초과하는 경우
3. **자금 효율화**: 매수 주문 시 현재가 대비 3%(`1.03`)의 버퍼를 적용하여 LOC 체결 확률을 높이면서도 가용 현금을 최대한 활용합니다.
4. **주문 유형 및 가격 로직**:
   - **매도 (Sell)**:
    - 초과분만큼 `현재가 - $0.01`로 **지정가(Limit) 매도** 주문
    - 목적: 시장가보다 조금 더 싸게 내놓아 즉시 체결 유도
- **매수 (Buy)**:
    - 부족분만큼 `현재가 + $0.01`로 **지정가(Limit) 매수** 주문
    - 목적: 시장가보다 조금 더 비싸게 주문하여 즉시 체결 유도
- **주문 순서**:
    - 매도 주문 먼저 실행 -> 현금 확보 -> 매수 주문 실행
5. **결과 예측**: 리포트에 주문 체결 후 예상되는 총 보유 금액과 비중(%)을 미리 보여줍니다.
6. **중복 주문 방지**: 스케줄러가 5분마다 실행되지만, LOC 주문은 장 마감 시 체결되어 장중에는 미체결 상태로 남습니다. `rebalancing_history.json`에 당일 실행 이력이 있으면 스킵하여 동일 주문이 반복 실행되는 것을 방지합니다. (`execute=True` 시에만 작동, 텔레그램 `/rebalance` 조회에는 영향 없음)

# Key Functions (주요 함수)

## `calculate_orders`
설정과 포트폴리오 데이터를 바탕으로 필요한 매수/매도 주문 리스트를 생성합니다.

- **입력 (Input)**:
  - `config` (Dict): `seed`, `assets`, `rebalance_threshold` 정보를 포함한 설정
  - `portfolio` (Dict): 현재 보유 종목 및 현금 잔고 정보
  - `current_prices` (Dict): 각 종목의 현재 시장가
  - `reserved_cash` (float): 다른 전략(RAOEO 등)을 위해 예약할 현금 (기본값: 0.0)
- **출력 (Output)**: `Tuple[List[StrategyOrder], Dict]`
   - `info["asset_status"]`에 각 자산별 `cur_w`(현재비중), `target_w`(목표비중), `diff_w`(괴리율) 정보 포함

# Configuration (`strategy_config.json`)

```json
{
  "rebalancing": {
    "enabled": true,
    "seed": 5000, // 목표 운용 자금 ($)
    "assets": [
      {"ticker": "TQQQ", "target_weight": 0.5},
      {"ticker": "SCHD", "target_weight": 0.5}
    ],
    "rebalance_threshold": 0.05 // 5%p 이상 괴리 시 작동
  }
}
```

# Usage Example (사용 예시)

```python
from strategy.rebalancing import calculate_orders

orders, info = calculate_orders(config, portfolio, prices)
for order in orders:
    print(order) # 예: [TQQQ] BUY 10 (50.89) ➔ Est.Total: $1,502.6 (50.0%)
```
