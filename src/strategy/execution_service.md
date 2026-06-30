# Execution Service (`src/strategy/execution_service.py`)

이 모듈은 모든 전략(`RAOEO`, `Value Averaging`, `Rebalancing`)의 실행주기를 관리하고 조율하는 역할을 합니다.

## Core Logic (핵심 로직)

1. **Unified Execution Flow (통합 실행 흐름)**:
   - 모든 전략은 `Enabled Check` -> `Market Check` -> `History Check` -> `Determine Action` -> `Execute` -> `Report`의 동일한 6단계 과정을 거칩니다.

2. **Centralized Market Status (시장 상태 중앙 관리)**:
   - `utils.market_utils`를 통해 휴장일 및 장 운영 시간을 확인하고, 이를 모든 전략 실행에 반영합니다.

3. **Unified Data Fetching (데이터 조회 통합)**:
   - `get_market_data`는 전략 대상의 보유 수량과 현재가를 조회합니다.
   - 현재가는 보유 잔고의 `cur_price`를 먼저 사용하고, 없는 종목만 Toss
     다건 현재가 API로 조회합니다. Toss에서 누락되거나 실패한 종목만 KIS
     단건 가격 조회로 보완합니다.
   - 전략 포트폴리오는 `strategy_config.json`의 `strategy_broker`가
     가리키는 계좌 scope만 사용합니다.
   - `StrategyRunContext`는 RAOEO/VA 같은 한 실행 묶음 안에서 포트폴리오와
     가격 스냅샷을 공유합니다. Telegram과 scheduler 모두 이 공통 경로를
     사용합니다.
   - 공식 KIS/Toss endpoint helper는 `execution_service`에서 직접
     import하지 않고 앱 소유 broker facade 뒤에서 호출합니다.

4. **Unified History Management (통합 히스토리 관리)**:
   - `strategy_history.json` 파일 하나에 모든 전략의 실행 결과를 날짜별로 통합 저장합니다.
   - 실행 이력이 있는 경우, 성공한 주문(`succeeded`)은 건너뛰고 실패한 주문(`pending`)만 선별하여 재실행을 시도합니다.
   - 사용자가 승인한 `cash_ticker` 조달 결과는 RAOEO의 `cash_funding_results`에 별도로 저장하여, 실패한 조달 주문이 일반 전략 재시도 주문으로 자동 실행되지 않게 합니다.
   - RAOEO 자동 실행에서 `normal`/`average` 매수 예산이 1주 가격에 미달해 주문이 없으면,
     해당 금액은 `skipped_buy_budgets`에 티커별 총액으로 저장되어 다음 RAOEO 계산에 이월됩니다.

5. **Timeout Handling (타임아웃 방어 메커니즘)**:
   - 외부 API 응답 지연을 방지하기 위하여 `requests.exceptions.Timeout` 에러를 독립적으로 포착합니다.
   - 타임아웃 발생 시, 스로틀이나 영구 정지 없이 `[API Timeout]` 메시지와 함께 사유를 로깅하고 `StrategyStatus.ERROR`로 무사히 보고를 마칩니다.

## Key Functions (주요 함수)

### `run_strategy_suite`
RAOEO와 Value Averaging을 같은 `StrategyRunContext`로 실행하여 포트폴리오와
가격 스냅샷을 공유합니다. Telegram `/strategy`와 scheduler 일일 주문 실행은
이 함수를 사용합니다.

### `run_raoeo_strategy`, `run_va_strategy`, `run_rebalancing_strategy`
각 전략을 실행하고 결과를 반환합니다.

- **입력 (Input)**:
  - `execute` (bool): `True`이면 실제 주문을 전송합니다. `False`이면 계산 결과만 반환합니다.
  - `run_rebalancing_strategy`의 `orderable_cache_key`는 자동 장중 점검에서만
    사용하며, 같은 미국 거래일에는 최초 `inquire_psamount` 결과를
    재사용해 반복 계좌 API 조회를 줄입니다.
- **출력 (Output)**: `Dict` (표준화된 리포트 객체)
  - `status`: 실행 결과 (`executed`, `partial`, `skipped`, `non_market_time`, `disabled`, `already_done` 등)
  - `orders`: 생성된 전체 주문 목록
  - `succeeded_orders`: 이미 체결 완료된 주문 목록
  - `pending_orders`: 체결 필요한(대기 중인) 주문 목록
  - `market_status`: 시장 상태 정보 (`is_market_open`, `message`)

### `get_market_data`
현재 포트폴리오 잔고와 전략 대상 종목들의 현재가를 조회합니다.
- **입력**: `force_refresh` (bool)
- **출력**: `holdings` (잔고 딕셔너리), `current_prices` (현재가 딕셔너리)
- 보유 잔고의 `cur_price`를 먼저 사용합니다. 가격이 없는 전략 대상만
  Toss 다건 현재가 API로 한 번에 조회하고, Toss 누락/실패 종목만 KIS
  단건 가격 조회로 보완합니다.
- 같은 실행 묶음에서는 `StrategyRunContext`가 포트폴리오/가격 스냅샷을
  재사용해 중복 포트폴리오 조회를 줄입니다.

### `get_orderable_usd`
대표 매수 주문의 종목과 주문 가격으로 선택된 전략 broker의
매수가능금액조회를 수행합니다.

- **입력**: `symbol` (str), `order_price` (float)
- **출력**: broker별 주문가능금액 API 기반의 주문가능 USD
- RAOEO의 `cash_ticker` 조달 부족분과 리밸런싱의 매수 여력 판단에
  사용합니다.
- Telegram 명령에 의한 확인은 항상 새로 조회하며, 자동 주기
  리밸런싱만 거래일 단위 조회 결과를 재사용합니다.

### `_execute_orders`
주문 목록을 받아 순차적으로 선택된 전략 broker API를 통해 실행합니다.

- **입력 (Input)**:
  - `orders` (List[StrategyOrder]): 실행할 주문 객체 리스트
  - `sell_first` (bool): 매도 주문 먼저 실행 여부 (리밸런싱용)
- **출력 (Output)**: `List[Dict]` (실행 결과 리스트: `success`, `message` 포함)
- 각 주문은 broker API 호출 직전에 `[OrderAudit] Preparing strategy order`
  로그를 남깁니다. 로그에는 실행 broker, ticker, 매수/매도, 수량, 주문가,
  예상 금액, 주문 타입, 주문 사유가 포함됩니다. 시장가처럼 주문가가 없는
  경우 예상 금액은 `unknown`으로 기록합니다.

### `prepare_raoeo_cash_funding`, `execute_raoeo_cash_funding`
`/strategy` 수동 실행에서만 사용하는 현금 조달 단계입니다.

- 현재 대기 중인 RAOEO 매수 주문에 대해 `get_orderable_usd`로 조회한
  해외주문가능금액만으로 부족분을 판단합니다. Toss 전략 broker에서는
  이미 포트폴리오 조회에 포함된 `USD cash` buying power를 재사용해
  중복 buying-power 조회를 피합니다. Value Averaging 주문은 조달 계산에
  포함하지 않습니다.
- 자동 스케줄의 `run_raoeo_strategy(execute=True)`는 `cash_ticker` 매도 주문을 만들지 않습니다.
- 사용자가 조달 매도를 선택한 경우에만 매도 주문을 접수하며, 접수 성공 후 5초 대기하고 후속 전략 실행으로 진행합니다.
- 조달 주문을 만들 수 없거나 주문 접수가 실패하면 호출자는 RAOEO와 Value Averaging 실행 모두를 중단합니다.

### `clear_strategy_history_for_date`
지정한 ET 날짜의 `strategy_history.json` 날짜 항목 전체를 삭제합니다. 텔레그램
`/clear_strategy_history` 같은 운영 UI는 이 함수를 호출해, 실패 주문 재테스트
전에 RAOEO/VA/rebalancing 이력을 한 번에 제거합니다.

## Configuration (`strategy_config.json`)

`strategy_broker`로 전략 실행 계좌를 선택하고, 각 전략 섹션
(`raoeo`, `value_averaging`, `rebalancing`)의 `enabled` 필드를 확인하여
실행 여부를 결정합니다.
RAOEO와 Value Averaging은 활성화된 target이 하나도 없으면 history 조회나
market data 조회 없이 `disabled` 상태로 종료합니다.
Value Averaging은 오늘 history가 있으면 `orders`가 비어 있어도 저장된
상태와 target context를 재사용하며 market data를 다시 조회하지 않습니다.

```json
{
  "strategy_broker": "kis",
  "raoeo": {
    "enabled": true, // 전략 전체 활성화 여부
    "targets": {
      "SOXL": { "enabled": true } // 개별 종목 활성화 여부
    }
  }
}
```

## Usage Example (사용 예시)

```python
from strategy.execution_service import run_raoeo_strategy

# 1. 단순 계산 및 리포트 확인 (주문 전송 X)
report = run_raoeo_strategy(execute=False)
print(report['status'])

# 2. 실제 주문 실행
if report['status'] == 'skipped' or report['status'] == 'partial':
    result = run_raoeo_strategy(execute=True)
```
