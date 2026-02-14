# Scheduler Order Service (`src/scheduler/scheduler_order.py`)

정해진 일정(예: 장 종료 직전)에 따라 **전략 실행(Execution)**을 담당하는 스케줄러 모듈입니다.
텔레그램 봇을 사용하지 않는 경우에도 자동으로 주문이 나가도록 설계되었습니다.

# Core Logic (핵심 로직)

1. **전략 실행 (RAOEO)**: `run_raoeo_strategy(execute=True)`를 호출하여 주문을 계산하고 실행합니다.
2. **전략 실행 (VA)**: `run_va_strategy(execute=True)`를 호출하여 주문을 계산하고 실행합니다.
3. **통합 보고서 생성**: `format_strategy_report`를 사용하여 실행 결과를 텍스트로 변환합니다.
4. **텔레그램 알림**: 생성된 보고서를 `send_notification`으로 전송합니다.

# Key Functions (주요 함수)

## `run_daily_order_report`
매일 밤 자동으로 실행되어야 하는 함수입니다.

- **기능**: 전략 계산 및 주문 자동 실행, 결과 보고서 전송.
- **예외 처리**: 실행 중 오류가 발생해도 로그를 남기고 다음 단계로 넘어갑니다.

# Configuration (`scheduler/scheduler.py` - Crontab)

```python
# scheduler.py 예시
scheduler.add_job(
    run_daily_order_report, 
    'cron', 
    day_of_week='mon-fri', 
    hour=22, minute=50
)
```

# Usage Example (사용 예시)

```python
from scheduler.scheduler_order import run_daily_order_report

# 수동 실행 (테스트)
run_daily_order_report()
```
