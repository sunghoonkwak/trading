# Execution Service (`src/strategy/execution_service.py`)

이 모듈은 모든 전략(`RAOEO`, `Value Averaging`, `Rebalancing`)의 실행주기를 관리하고 조율하는 역할을 합니다.

# Core Logic (핵심 로직)

1. **Unified Execution Flow (통합 실행 흐름)**:
   - 모든 전략은 `Enabled Check` -> `Market Check` -> `History Check` -> `Determine Action` -> `Execute` -> `Report`의 동일한 6단계 과정을 거칩니다.

2. **Centralized Market Status (시장 상태 중앙 관리)**:
   - `utils.market_utils`를 통해 휴장일 및 장 운영 시간을 확인하고, 이를 모든 전략 실행에 반영합니다.

3. **Unified History Management (통합 히스토리 관리)**:
   - `strategy_history.json` 파일 하나에 모든 전략의 실행 결과를 날짜별로 통합 저장합니다.
   - 실행 이력이 있는 경우, 성공한 주문(`succeeded`)은 건너뛰고 실패한 주문(`pending`)만 선별하여 재실행을 시도합니다.

# Key Functions (주요 함수)

## `run_raoeo_strategy`, `run_va_strategy`, `run_rebalancing_strategy`
각 전략을 실행하고 결과를 반환합니다.

- **입력 (Input)**:
  - `execute` (bool): `True`이면 실제 주문을 전송합니다. `False`이면 계산 결과만 반환합니다.
- **출력 (Output)**: `Dict` (표준화된 리포트 객체)
  - `status`: 실행 결과 (`executed`, `partial`, `skipped`, `holiday`, `disabled` 등)
  - `orders`: 생성된 전체 주문 목록
  - `succeeded_orders`: 이미 체결 완료된 주문 목록
  - `pending_orders`: 체결 필요한(대기 중인) 주문 목록
  - `market_status`: 시장 상태 정보 (`is_market_open`, `message`)

## `_execute_orders`
주문 목록을 받아 순차적으로 KIS API를 통해 실행합니다.

- **입력 (Input)**:
  - `orders` (List[StrategyOrder]): 실행할 주문 객체 리스트
  - `sell_first` (bool): 매도 주문 먼저 실행 여부 (리밸런싱용)
- **출력 (Output)**: `List[Dict]` (실행 결과 리스트: `success`, `message` 포함)

# Configuration (`strategy_config.json`)

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

# Usage Example (사용 예시)

```python
from strategy.execution_service import run_raoeo_strategy

# 1. 단순 계산 및 리포트 확인 (주문 전송 X)
report = run_raoeo_strategy(execute=False)
print(report['status'])

# 2. 실제 주문 실행
if report['status'] == 'skipped' or report['status'] == 'partial':
    result = run_raoeo_strategy(execute=True)
```
