# Strategy Execution Service (`src/strategy/execution_service.py`)

전략 실행의 **중앙 제어 타워** 역할을 하는 서비스 모듈입니다.
데이터 조회, 전략 계산, 주문 실행, 이력 저장, 보고서 생성 등 전체 프로세스를 조율(Orchestration)합니다.

# Core Logic (핵심 로직)

1. **데이터 준비**: 포트폴리오(KIS API), 현재가, 설정 파일 등을 로드합니다. 리밸런싱의 경우 KIS 계좌로 범위를 제한(Scope filtering)합니다.
2. **전략 계산**: `raoeo`, `value_averaging`, `rebalancing` 모듈의 함수를 호출하여 주문 목록을 생성합니다. 휴장일에도 계산은 수행하여 보고서에 포함합니다.
3. **주문 실행**: `execute=True` 플래그가 있으면 KIS API를 통해 실제 주문을 전송합니다.
4. **안전 집행 (Rebalancing)**: 리밸런싱의 경우 매도 대금이 입금될 시간을 확보하기 위해 **매도 우선 실행 후 60초 대기**, 그 다음 매수를 실행합니다.
5. **이력 저장**: 실행 결과를 각 전략별 JSON 파일로 저장합니다.

# Key Functions (주요 함수)

## `run_raoeo_strategy` / `run_va_strategy`
각 전략의 전체 사이클(조회 -> 계산 -> 실행)을 수행합니다.

## `run_rebalancing_strategy`
리밸런싱 전략 전용 사이클을 수행합니다. KIS 전용 데이터를 사용하며, 안전 집행 로직이 포함되어 있습니다.

## `execute_single_order`
개별 `StrategyOrder` 객체를 KIS API 포맷으로 변환하여 실행합니다. 미국 주식의 경우 시장가 매도 효과를 위해 아주 낮은 지정가(0.01) 매도를 지원합니다.

# Usage Example (사용 예시)

```python
from strategy.execution_service import run_rebalancing_strategy

# 실제 주문 실행 (매도 후 60초 대기 로직 포함)
result = run_rebalancing_strategy(execute=True)
```
