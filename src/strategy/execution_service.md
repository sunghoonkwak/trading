# Strategy Execution Service (`src/strategy/execution_service.py`)

전략 실행의 **중앙 제어 타워** 역할을 하는 서비스 모듈입니다.
데이터 조회, 전략 계산, 주문 실행, 이력 저장, 보고서 생성 등 전체 프로세스를 조율(Orchestration)합니다.

# Core Logic (핵심 로직)

1. **데이터 준비**: 포트폴리오(KIS API), 현재가, 설정 파일 등을 로드합니다.
2. **전략 계산**: `raoeo`나 `value_averaging` 모듈의 순수 함수를 호출하여 주문 목록을 생성합니다.
3. **휴장일 체크**: 휴장일인 경우 실행을 막고 상태를 보고합니다.
4. **주문 실행**: `execute=True` 플래그가 있으면 KIS API를 통해 실제 주문을 전송합니다.
5. **이력 저장**: 실행 결과를 JSON 파일로 저장합니다.

# Key Functions (주요 함수)

## `run_raoeo_strategy`
RAOEO 전략의 전체 사이클(조회 -> 계산 -> 실행)을 수행합니다.

- **입력 (Input)**: `execute` (bool): 주문 실행 여부 (False면 계산만 수행).
- **출력 (Output)**: `dict` (보고서 데이터 - 주문 목록, 실행 결과 등).

## `run_va_strategy`
Value Averaging 전략의 전체 사이클을 수행합니다.

- **입력 (Input)**: `execute` (bool): 주문 실행 여부.
- **출력 (Output)**: `dict` (보고서 데이터).

## `execute_single_order`
개별 `StrategyOrder` 객체를 KIS API 포맷으로 변환하여 실행합니다.

# Configuration (None)
이 모듈은 독자적인 설정 파일이 없으며, `strategy_config.json`과 `kis_config` 등을 참조합니다.

# Usage Example (사용 예시)

```python
from strategy.execution_service import run_raoeo_strategy

# 1. 단순 보고서 생성 (계산만)
report = run_raoeo_strategy(execute=False)
print(report['orders'])

# 2. 실제 주문 실행
result = run_raoeo_strategy(execute=True)
```
