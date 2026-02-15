# RAOEO Strategy (`src/strategy/raoeo.py`)

**RAOEO 무한 매수법**의 순수 계산 로직을 구현한 모듈입니다.
현재 보유량과 시장가를 기준으로 일일 매수/매도 주문을 결정하며, 정해진 기간 동안 꾸준히 매집하면서 수익을 실현하는 것을 목표로 합니다.

# Core Logic (핵심 로직)

전체 투자금(`seed`)을 일일 예산(`seed / duration`)으로 나누고, 현재 매집 진행률(소모 금액)에 따라 3단계 페이즈로 나누어 매수 강도를 조절합니다.

| Phase | 소모 금액 % | 동작 (Action) |
|-------|---------|--------|
| **0** | < 10% | 공격적 매수 + 보유량 10%까지 추가 매수 (Fill) |
| **1** | 10-50% | 일반적인 일일 예산만큼 매수 |
| **2** | > 50% | 분할 매수: 50%는 평단가, 50%는 목표가(Target Price) |

**매도 로직**: 보유량이 2주 이상이면, 항상 `(보유량 - 1)`의 50%를 `평단가 × (1 + 수익률)` 가격에 매도 주문을 냅니다.

# Key Functions (주요 함수)

## `calculate_orders`
실행 가능한 매수/매도 주문 목록을 생성합니다.

- **입력 (Input)**:
  - `targets_config` (dict): 종목별 설정 (시드머니, 기간 등).
  - `portfolio` (dict): 현재 보유 현황 (수량, 평단가).
  - `current_prices` (dict): 실시간 현재가.
- **출력 (Output)**: `List[StrategyOrder]` (실행할 주문 객체 리스트)

# Logging & Monitoring (로깅 및 모니터링)

- **요약 로그**: 각 종목별로 계산이 완료될 때마다 다음 정보를 `INFO` 레벨로 기록합니다.
    - 현재 단계 (Phase 0, 1, 2)
    - 투자 진척도 (보유 금액 / 전체 시드머니 및 백분율)
    - 생성된 주문 요약 (매수 및 매도 주문 개수)
- **경고 로그**: 가격 데이터가 없거나 설정값이 유효하지 않은 경우 `WARNING` 또는 `ERROR` 로그를 남깁니다.

# Configuration (`strategy_config.json`)

```json
{
  "raoeo": {
    "targets": {
      "SOXL": {
        "seed": 1000,       // 총 투자 금액 ($)
        "duration": 40,     // 투자 기간 (일)
        "sell_profit": 0.10 // 목표 수익률 (10%)
      }
    }
  }
}
```

# Usage Example (사용 예시)

```python
from strategy.raoeo import calculate_orders

# 데이터 준비
config = {"SOXL": {"seed": 1000, "duration": 40}}
holdings = {"SOXL": {"qty": 10, "avg_price": 35.0}}
prices = {"SOXL": 34.5}

# 주문 계산
orders = calculate_orders(config, holdings, prices)
```
