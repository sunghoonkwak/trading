# RAOEO Strategy (`src/strategy/raoeo.py`)

이 모듈은 RAOEO (Reverse Accumulating Order Execution) 전략의 순수 계산 로직을 담당합니다. 마켓 상태나 실행 여부와 관계없이 설정과 현재가에 기반한 주문을 생성합니다.
기존의 하드코딩되었던 Phase 체계에서 벗어나, `strategy_config.json`의 `phase` 배열 설정에 따라 유동적으로 작동하도록 개편되었습니다.

# Core Logic (핵심 로직)

1. **Pure Function (순수 함수)**:
   - 외부 API 호출이나 상태 변경 없이, 입력값(`config`, `portfolio`, `price`)만으로 주문을 계산합니다.

2. **Order Calculation (주문 계산)**:
   - `strategy_config.json`에 정의된 `targets.[TICKER].phase` 배열을 위에서부터 차례대로 판독합니다.
   - 보유 자본금 대비 사용된 금액(`spent_amount / seed`)의 비율이 `threshold` 미만일 때 해당 Phase의 룰(`buy` 및 `sell`)을 채택하여 주문을 계산합니다. 마지막 원소인 경우 기본(fallback) 설정으로 `threshold` 없이 동작할 수 있습니다.
   - **매도 로직 (Sell)**:
     - `sell` 배열 내 각 항목(type, ratio, profit)에 따라 보유 수량을 분할하여 한도와 목표가를 정합니다. (`LOC` 혹은 `Limit` 주문)
   - **매수 로직 (Buy)**:
     - 공통 로직: `buy_price = (min(price_percent_cap, 최저목표수익률) + 1) * 평단가 - 0.01` 기반으로 산출됩니다.
     - `type: "normal"`: `price_percent_cap: 0.1`로 설정하여 목표 수익률에 연동시킵니다.
     - `type: "average"`: `price_percent_cap: 0.0`으로 설정하여 평단가 근처에서 매수되게 유도합니다.
     - `type: "filling"`: `price_percent_cap: -0.05` 등으로 설정하여 평단가 대비 할인된 가격에 매수하며, `target_ratio`에 다다를 때까지의 부족분 수량을 보충(Fill) 매수합니다.

3. **Buy Price Cap (매수 가격 상한)**:
   - KIS는 현재가의 30% 초과 매수 주문을 거절하므로, 안전 마진을 두고 **25%** 캡을 적용합니다.
   - `_cap_buy_price()`: 계산된 매수 가격이 `cur_price * 1.25`를 초과하면 캡으로 제한합니다.
   - 상수 `MAX_BUY_PRICE_RATIO = 1.25`로 관리됩니다.

4. **Configuration Validation (설정 검증)**:
   - `seed > 0`, `duration > 0` 여부를 검증합니다.
   - Phase 내 `buy`/`sell` 비율(0.0~2.0) 및 `profit`(0.0~0.5), 그리고 허용된 매수 타입(`normal`, `average`, `filling`)인지 검증합니다.
   - 잘못된 설정 발견 시 `ValueError` 예외를 발생시켜 시스템 오작동을 선제적으로 차단합니다.

# Key Functions (주요 함수)

## `calculate_orders`
설정과 시장 데이터를 기반으로 설정된 Phase에 맞추어 매수/매도 주문을 동적 계산합니다.

- **입력 (Input)**:
  - `targets_config` (Dict): 종목별 설정 (seed, duration, **phase** 등)
  - `portfolio` (Dict): 현재 보유 잔고 (qty, avg_price 등)
  - `current_prices` (Dict): 현재 시장가
  - `exchange_rates` (Optional[Dict]): 환율 정보
  - `cash_ticker` (str): 매수 대금 부족 시 매도할 현금성 ETF 티커 (예: "TLTW")
- **출력 (Output)**: `Tuple[List[StrategyOrder], Dict]` (주문 목록, 메타 정보)
- **현금 조달 로직 (Cash Funding)**:
  - 매수 주문 총액을 계산한 후, 보유 중인 `USD cash`를 우선적으로 차감합니다.
  - 부족분(Shortfall)이 존재할 경우에만 `cash_ticker`를 매도하여 현금을 조달합니다.
  - 무보유 공매도를 방지하기 위해 `cash_ticker`의 매도 수량은 항상 실제 보유 수량으로 캡(Cap)이 적용됩니다. 이 매도 주문은 다른 주문보다 우선적으로 실행되도록 주문 목록 맨 앞(index 0)에 추가됩니다.

# Configuration (`strategy_config.json`)

```json
{
  "raoeo": {
    "enabled": true,
    "targets": {
      "SOXL": {
        "enabled": true,
        "seed": 20000,
        "duration": 40,
        "phase": [
          {
             "name": "Phase 0, quick filling",
             "_description": "Phase별 고유의 매수/매도 로직 설정",
             "threshold": 0.1,
             "buy": [
               { "type": "normal", "ratio": 1, "price_percent_cap": 0.1 },
               { "type": "filling", "price_percent_cap": -0.05, "target_ratio": 0.1 }
             ],
             "sell": [
               { "type": "LOC", "ratio": 0.5, "profit": 0.2 },
               { "type": "Limit", "ratio": 0.5, "profit": 0.2 }
             ]
          }
          // 더 많은 Phase들 추가 정의 가능 (threshold는 오름차순으로)
        ]
      }
    }
  }
}
```
