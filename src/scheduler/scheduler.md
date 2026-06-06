# Scheduler Service (`src/scheduler/scheduler.py`)

이 모듈은 시스템의 예약된 작업을 총괄하는 메인 스케줄러입니다.

## Structure (구조)

- `scheduler.py`: 스케줄러 초기화 및 작업 등록 (`Main Entry`)
- `scheduler_portfolio.py`: 포트폴리오 리포트 로직 (`Job Reference`)
- `scheduler_order.py`: 주문(RAOEO/VA) 리포트 로직 (`Job Reference`)

## Dependencies (의존성)

```bash
pip install schedule pytz
```

## Public API (`scheduler.py`)

### `start_scheduler`
스케줄러를 초기화하고 백그라운드 스레드에서 `run_scheduler_loop`를 시작합니다.
다음의 작업들을 예약합니다:
- **07:00 KST**: 포트폴리오 리포트 (`run_daily_portfolio_report`) — KST 고정
- **07:00 ET → KST 동적 계산**: 주문 리포트 (`run_daily_order_report`) — EST: 21:00 KST / EDT: 20:00 KST
- **매 5분**: 리밸런싱 (`run_periodic_rebalancing`) — 내부에서 09:40~15:40 ET 윈도우 체크
- **00:05 KST**: DST 변경 감지 및 자동 재스케줄 (`_reschedule_if_dst_changed`)

### `run_scheduler_loop`
백그라운드 데몬 스레드에서 실행되며, 1분마다 `schedule.run_pending()`을 호출하여 예약된 작업이 있는지 확인하고 실행합니다.

## DST (섬머타임) 대응

주문 리포트는 미국 동부시간(ET) 기준으로 스케줄링됩니다:
- `_et_to_kst()`: ET 시간을 KST로 변환 (DST 자동 반영)
- `_reschedule_if_dst_changed()`: 매일 00:05 KST에 DST 전환 감지 → 스케줄 재설정
- `ORDER_REPORT_ET`: 목표 ET 시간 상수 `(7, 0)` — 07:00 ET

## Usage Example (사용 예시)

```python
from scheduler.scheduler import start_scheduler

# 메인 프로세스 시작 시 호출
start_scheduler()
```
