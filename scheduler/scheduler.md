# Scheduler Service (`scheduler.py`)

이 모듈은 시스템의 예약된 작업을 총괄하는 메인 스케줄러입니다.

## Structure (구조)

- `scheduler.py`: 스케줄러 초기화 및 작업 등록 (`Main Entry`)
- `scheduler_portfolio.py`: 포트폴리오 리포트 로직 (`Job Reference`)
- `scheduler_order.py`: 주문(RAOEO/VA) 리포트 로직 (`Job Reference`)

## Dependencies (의존성)

```bash
pip install schedule
```

## Public API (`scheduler.py`)

### start_scheduler
스케줄러를 초기화하고 백그라운드 스레드에서 `run_scheduler_loop`를 시작합니다.
다음의 데일리 작업들을 예약합니다:
- **07:00**: 포트폴리오 리포트 (`run_daily_portfolio_report`)
- **21:00**: 주문 리포트 (`run_daily_order_report`)

### run_scheduler_loop
백그라운드 데몬 스레드에서 실행되며, 10분마다 `schedule.run_pending()`을 호출하여 예약된 작업이 있는지 확인하고 실행합니다.

## Usage Example

```python
from scheduler.scheduler import start_scheduler

# 메인 프로세스 시작 시 호출
start_scheduler()
```
