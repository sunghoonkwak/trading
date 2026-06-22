# Scheduler Order Service (`src/scheduler/scheduler_order.py`)

정해진 일정에 따라 **전략 실행(Execution)**을 담당하는 스케줄러 모듈입니다.
매일 밤 정해진 시간 또는 장중에 주기적으로 주문을 실행하도록 설계되었습니다.

## Core Logic (핵심 로직)

1. **데일리 전략 (RAOEO/VA)**: 매일 밤 정해진 시간(예: 21:00)에
   `execution_service.run_strategy_suite`로 통합 보고서를 생성하고 주문을
   실행합니다. RAOEO와 VA는 같은 실행 컨텍스트를 공유해 포트폴리오/가격
   조회를 반복하지 않습니다.
2. **주기적 리밸런싱**: US/Eastern 장중 시간(09:40 ~ 15:40 ET) 동안 5분 간격으로 비중을 체크하고 리밸런싱을 수행합니다. 매수가능 USD는 같은 미국 거래일의 첫 `inquire_psamount` 조회 결과를 재사용하여 계좌 API 호출을 반복하지 않습니다.
3. **지능형 알림**:
   - 데일리 전략은 항상 결과를 보고합니다.
   - 리밸런싱은 US/Eastern 기준 해당 날짜의 **첫 스케줄 호출** 시 `already_done` 상태라도 알림을 보냅니다.
   - 이후 호출에서는 새로운 실행(`executed`, `partial`)이나 타임아웃 등의 치명적 통신 오류(`error`) 발생 시에만 알림을 보냅니다. 특히 **네트워크 타임아웃(API 응답 무반응) 발생 시 텔레그램 긴급 알림**을 통해 유저가 인지할 수 있도록 보장합니다.

## Key Functions (주요 함수)

### `run_daily_order_report`
매일 밤 RAOEO 및 VA 전략을 공통 실행 묶음으로 실행합니다.

### `run_periodic_rebalancing`
리밸런싱 전용 주기적 실행 함수입니다. US/Eastern 시간 윈도우 체크 및 날짜 플래그 기반 첫 알림 로직이 포함되어 있습니다.

## Configuration (`scheduler/scheduler.py`)

```python
# 5분마다 리밸런싱 체크
schedule.every(5).minutes.do(run_periodic_rebalancing)
```

## Usage Example (사용 예시)

```python
from scheduler.scheduler_order import run_periodic_rebalancing

# 리밸런싱 루틴 수동 실행
run_periodic_rebalancing()
```
