# Execution Service (`src/strategy/execution_service.py`)

이 모듈은 모든 전략(`RAOEO`, `Value Averaging`, `Rebalancing`)의 실행주기를 관리하고 조율하는 역할을 합니다.

## Core Logic (핵심 로직)

1. **Unified Execution Flow (통합 실행 흐름)**:
   - 모든 전략은 `Enabled Check` -> `Market Check` -> `History Check` -> `Determine Action` -> `Execute` -> `Report`의 동일한 6단계 과정을 거칩니다.

2. **Centralized Market Status (시장 상태 중앙 관리)**:
   - `utils.market_utils`를 통해 휴장일 및 장 운영 시간을 확인하고, 이를 모든 전략 실행에 반영합니다.

3. **Unified Data Fetching (데이터 조회 통합)**:
   - `get_market_data`는 전략 대상의 보유 수량과 현재가를 조회합니다.
   - 현재가는 `utils.price_utils.resolve_current_price`의 공통 규칙을 따릅니다.
     직접 조회한 현재가를 우선 사용하고, 유효하지 않으면 보유 잔고의
     `cur_price`로 fallback합니다.
   - 매수 가능 USD는 포트폴리오의 `USD cash`에서 가져오지 않고,
     `get_orderable_usd`가 `broker.kis_broker`를 통해 KIS
     `inquire_psamount`의 `ovrs_ord_psbl_amt`를 읽어 제공합니다.
   - 공식 KIS endpoint wrapper는 `execution_service`에서 직접 import하지
     않고 앱 소유 broker facade 뒤에서 호출합니다.

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

### `run_raoeo_strategy`, `run_va_strategy`, `run_rebalancing_strategy`
각 전략을 실행하고 결과를 반환합니다.

- **입력 (Input)**:
  - `execute` (bool): `True`이면 실제 주문을 전송합니다. `False`이면 계산 결과만 반환합니다.
  - `run_rebalancing_strategy`의 `orderable_cache_key`는 자동 장중 점검에서만
    사용하며, 같은 미국 거래일에는 최초 `inquire_psamount` 결과를
    재사용해 반복 계좌 API 조회를 줄입니다.
- **출력 (Output)**: `Dict` (표준화된 리포트 객체)
  - `status`: 실행 결과 (`executed`, `partial`, `skipped`, `holiday`, `disabled`, `already_done` 등)
  - `orders`: 생성된 전체 주문 목록
  - `succeeded_orders`: 이미 체결 완료된 주문 목록
  - `pending_orders`: 체결 필요한(대기 중인) 주문 목록
  - `market_status`: 시장 상태 정보 (`is_market_open`, `message`)

### `get_market_data`
현재 포트폴리오 잔고와 전략 대상 종목들의 현재가를 조회합니다.
- **입력**: `force_refresh` (bool)
- **출력**: `holdings` (잔고 딕셔너리), `current_prices` (현재가 딕셔너리)
- 현재가 조회 실패 시 보유 잔고의 `cur_price`를 사용하며, 두 값 모두
  유효하지 않으면 해당 종목은 `current_prices`에 포함하지 않습니다.

### `get_orderable_usd`
대표 매수 주문의 종목, 거래소, 주문 가격으로 해외주식
매수가능금액조회를 수행합니다.

- **입력**: `symbol` (str), `order_price` (float)
- **출력**: `ovrs_ord_psbl_amt` 기반의 해외주문가능 USD
- RAOEO의 `cash_ticker` 조달 부족분과 리밸런싱의 매수 여력 판단에
  사용합니다.
- Telegram 명령에 의한 확인은 항상 새로 조회하며, 자동 주기
  리밸런싱만 거래일 단위 조회 결과를 재사용합니다.

### `_execute_orders`
주문 목록을 받아 순차적으로 KIS API를 통해 실행합니다.

- **입력 (Input)**:
  - `orders` (List[StrategyOrder]): 실행할 주문 객체 리스트
  - `sell_first` (bool): 매도 주문 먼저 실행 여부 (리밸런싱용)
- **출력 (Output)**: `List[Dict]` (실행 결과 리스트: `success`, `message` 포함)

### `prepare_raoeo_cash_funding`, `execute_raoeo_cash_funding`
`/strategy` 수동 실행에서만 사용하는 현금 조달 단계입니다.

- 현재 대기 중인 RAOEO 매수 주문에 대해 `get_orderable_usd`로 조회한
  해외주문가능금액만으로 부족분을 판단하며, 이 단계에서만
  `cash_ticker` 시세를 추가 조회합니다. Value Averaging 주문은 조달
  계산에 포함하지 않습니다.
- 자동 스케줄의 `run_raoeo_strategy(execute=True)`는 `cash_ticker` 매도 주문을 만들지 않습니다.
- 사용자가 조달 매도를 선택한 경우에만 매도 주문을 접수하며, 접수 성공 후 5초 대기하고 후속 전략 실행으로 진행합니다.
- 조달 주문을 만들 수 없거나 주문 접수가 실패하면 호출자는 RAOEO와 Value Averaging 실행 모두를 중단합니다.

## Configuration (`strategy_config.json`)

각 전략 섹션(`raoeo`, `value_averaging`, `rebalancing`)의 `enabled` 필드를 확인하여 실행 여부를 결정합니다.

```json
{
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
