# RAOEO Strategy (`src/strategy/raoeo.py`)

이 모듈은 RAOEO (Reverse Accumulating Order Execution) 전략의 순수 계산 로직을 담당합니다. 마켓 상태나 실행 여부와 관계없이 설정과 현재가에 기반한 주문을 생성합니다.
기존의 하드코딩되었던 Phase 체계에서 벗어나, `strategy_config.json`의 `phase` 배열 설정에 따라 유동적으로 작동하도록 개편되었습니다.

## Core Logic (핵심 로직)

1. **Pure Function (순수 함수)**:
   - 외부 API 호출이나 상태 변경 없이, 입력값(`config`, `portfolio`, `price`)만으로 주문을 계산합니다.
   - 현재가는 `utils.price_utils.resolve_current_price`를 통해
     `current_prices` 우선, 보유 잔고의 `cur_price` fallback 순서로 해석합니다.

2. **Order Calculation (주문 계산)**:
   - `strategy_config.json`에 정의된 `targets.[TICKER].phase` 배열을 위에서부터 차례대로 판독합니다.
   - 보유 자본금 대비 사용된 금액(`spent_amount / seed`)의 비율이 `threshold` 미만일 때 해당 Phase의 룰(`buy` 및 `sell`)을 채택하여 주문을 계산합니다. 마지막 원소인 경우 기본(fallback) 설정으로 `threshold` 없이 동작할 수 있습니다.
   - 생성된 `StrategyOrder.order_type`은 KIS/Toss 코드가 아니라 `LIMIT`, `LOC` 같은 브로커 독립 주문 의도입니다. 실제 API 주문 코드는 선택된 broker facade에서 변환합니다.
   - **매도 로직 (Sell)**:
     - `sell` 배열 내 각 항목(type, ratio, profit)에 따라 보유 수량을 분할하여 한도와 목표가를 정합니다. (`LOC` 혹은 `Limit` 주문)
   - **매수 로직 (Buy)**:
     - 공통 로직: `buy_price = (min(price_percent_cap, 최저목표수익률) + 1) * 평단가 - 0.01` 기반으로 산출됩니다.
     - `type: "normal"`: `price_percent_cap: 0.1`로 설정하여 목표 수익률에 연동시킵니다.
     - `type: "average"`: `price_percent_cap: 0.0`으로 설정하여 평단가 근처에서 매수되게 유도합니다.
     - `normal`/`average` 예산이 주문가 기준 1주에 미달하면 해당 매수 주문은 생성하지 않습니다.
     - 한 Phase에 `normal`과 `average`가 함께 있으면 `normal`을 먼저 해당 비율 예산으로 계산하고,
       `normal` 주문금액을 제외한 나머지 전체 예산을 `average` 예산으로 사용합니다.
     - `type: "filling"`: `price_percent_cap: -0.05` 등으로 설정하여 평단가 대비 할인된 가격에 매수하며, `target_ratio`에 다다를 때까지의 부족분 수량을 보충(Fill) 매수합니다.

3. **Buy Price Cap (매수 가격 상한)**:
   - KIS는 현재가의 30% 초과 매수 주문을 거절하므로, 안전 마진을 두고 **25%** 캡을 적용합니다.
   - `_cap_buy_price()`: 계산된 매수 가격이 `cur_price * 1.25`를 초과하면 캡으로 제한합니다.
   - 상수 `MAX_BUY_PRICE_RATIO = 1.25`로 관리됩니다.

4. **Buy Budget Carryover (매수 예산 이월)**:
   - 매일 `seed / duration`에 이전 이월 예산을 더해 티커별 당일 매수 예산 풀을 만듭니다.
   - `normal` 및 `average` 매수 주문은 주문가 기준 목표 예산(`target_budget`)을 history에 저장합니다.
   - 다음 RAOEO 계산 시 가장 최근 이전 history에서 성공한 `Buy Normal`/`Buy Average` 주문의
     `target_budget - (qty * price)` 차액을 티커별 이월 예산에 더합니다.
   - 예산이 주문가 기준 1주에 미달해 주문이 생성되지 않은 `normal`/`average` 예산은
     `skipped_buy_budgets`에 티커별 총액으로 저장하고 다음 계산 시 당일 예산 풀에 전액 더합니다.
   - `normal`과 `average`가 함께 있는 Phase에서는 `normal` 미사용 예산이 당일 `average` 예산에
     포함되므로, 같은 금액을 이월 예산으로 중복 저장하지 않습니다.
   - `filling` 매수는 금액이 아니라 목표 수량을 보충하는 규칙이므로 예산 이월 대상에서 제외합니다.
   - 실제 체결가가 아니라 주문가 기준 보정입니다. 체결가 기준 보정은 별도의 체결내역 조회가 필요합니다.

5. **Configuration Validation (설정 검증)**:
   - `seed > 0`, `duration > 0` 여부를 검증합니다.
   - Phase 내 `buy`/`sell` 비율(0.0~2.0) 및 `profit`(0.0~0.5), 그리고 허용된 매수 타입(`normal`, `average`, `filling`)인지 검증합니다.
   - 잘못된 설정 발견 시 `ValueError` 예외를 발생시켜 시스템 오작동을 선제적으로 차단합니다.

## Key Functions (주요 함수)

### `calculate_orders`
설정과 시장 데이터를 기반으로 설정된 Phase에 맞추어 매수/매도 주문을 동적 계산합니다.

- **입력 (Input)**:
  - `targets_config` (Dict): 종목별 설정 (seed, duration, **phase** 등)
  - `portfolio` (Dict): 현재 보유 잔고 (qty, avg_price 등)
  - `current_prices` (Dict): 현재 시장가. 값이 없거나 0 이하이면 해당
    보유 잔고의 `cur_price`를 fallback으로 사용합니다.
  - `exchange_rates` (Optional[Dict]): 환율 정보
  - `history_data` (Optional[List[Dict]]): 주문가 기준 매수 예산 이월 계산에 사용할 strategy history
  - `today_date` (Optional[str]): 당일 history를 이월 대상으로 오인하지 않도록 제외할 날짜
  - `cash_ticker`는 `calculate_orders`가 자동 매도에 사용하는 입력이 아닙니다. 수동 조달 승인 경로에서 `calculate_cash_funding_order`에 전달됩니다.
- **출력 (Output)**: `Tuple[List[StrategyOrder], Dict]` (주문 목록, 메타 정보)

### `calculate_cash_funding_order`
텔레그램 수동 승인 시에만 RAOEO 대기 매수 주문의 현금 조달 주문을 계산합니다.

- 부족분은 포트폴리오의 `USD cash`가 아니라 KIS
  `inquire_psamount`가 반환한 `orderable_usd`를 기준으로 계산합니다.
- 부족분이 없으면 조달 주문을 만들지 않습니다.
- 부족분이 있지만 `cash_ticker` 가격 또는 충분한 보유 수량이 없으면 오류 정보를 반환하며, 부분 매도는 만들지 않습니다.
  `cash_ticker` 가격도 `current_prices` 우선, 보유 잔고의 `cur_price`
  fallback 순서로 해석합니다.
- 조달 주문은 자동 스케줄 실행의 RAOEO 주문 목록에 포함되지 않습니다.

## Configuration (`strategy_config.json`)

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
