# Scheduler Order Service (`src/scheduler/scheduler_order.py`)

정해진 일정에 따라 **전략 실행(Execution)**을 담당하는 스케줄러 모듈입니다.
매일 밤 정해진 시간 또는 장중에 주기적으로 주문을 실행하도록 설계되었습니다.

# Core Logic (핵심 로직)

1. **데일리 전략 (RAOEO/VA)**: 매일 밤 정해진 시간(예: 21:00)에 통합 보고서를 생성하고 주문을 실행합니다.
2. **주기적 리밸런싱**: 미국 장중 시간(23:40 ~ 05:40) 동안 5분 간격으로 비중을 체크하고 리밸런싱을 수행합니다.
3. **지능형 알림**: 
   - 데일리 전략은 항상 결과를 보고합니다.
   - 리밸런싱은 23:40 첫 보고 시 무조건 알림을 보내고, 그 외에는 실제 주문이나 에러가 발생한 경우에만 알림을 보냅니다.

# Key Functions (주요 함수)

## `run_daily_order_report`
매일 밤 RAOEO 및 VA 전략을 실행합니다.

## `run_periodic_rebalancing`
리밸런싱 전용 주기적 실행 함수입니다. 시간 윈도우 체크 로직이 포함되어 있습니다.

# Configuration (`scheduler/scheduler.py`)

```python
# 5분마다 리밸런싱 체크
schedule.every(5).minutes.do(run_periodic_rebalancing)
```

# Usage Example (사용 예시)

```python
from scheduler.scheduler_order import run_periodic_rebalancing

# 리밸런싱 루틴 수동 실행
run_periodic_rebalancing()
```
