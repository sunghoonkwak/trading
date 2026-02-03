# Order Report Scheduler (`scheduler_order.py`)

이 모듈은 매일 오후 9시에 실행되는 자동 주문 리포트(RAOEO, Value Averaging) 로직을 담당합니다.

## Public API (`scheduler_order.py`)

### run_daily_order_report
매일 저녁 실행되어 현재 설정된 트레이딩 전략(RAOEO, Value Averaging)의 상태를 점검하고 리포트를 생성합니다.
RAOEO와 Value Averaging 각각의 리포트를 생성한 뒤, 하나의 통합 메시지로 합쳐 텔레그램으로 전송합니다.

- **RAOEO Report**: `menu.raoeo.raoeo.get_daily_report()`를 호출하여 전략 상태를 가져오고 포맷팅합니다.
- **Value Averaging Output**: `menu.portfolio.value_averaging.get_daily_report()`를 호출하여 주문 필요 여부를 계산합니다. 주문이 필요 없는 경우 `type='skip'` 결과를 생성하여 리포트에 포함시킵니다.

### Helpers (Imported)

- **format_raoeo_report(report)**: `telegram_bot.telegram_raoeo`에서 가져옴. RAOEO 리포트를 텔레그램 메시지 포맷으로 변환합니다.
- **format_va_report(res)**: `telegram_bot.telegram_portfolio`에서 가져옴. Value Averaging 결과를 텔레그램 메시지 포맷으로 변환합니다.

## Dependencies
- `telegram_bot.telegram_utils`: 메시지 전송 (`send_notification`)
- `menu.raoeo`: RAOEO 로직
- `menu.portfolio`: Value Averaging 로직
