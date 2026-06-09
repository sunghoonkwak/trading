# Order Admin Facade (`src/broker/order_admin.py`)

이 모듈은 앱 소유 영역에서 미체결 주문 조회와 주문 관리 액션 경계를 제공합니다.

## Responsibilities

- `fetch_open_orders()`를 제공합니다.
- `execute_manage_action(market, action_type, order_data, new_price=None)`를 제공합니다.
- `sync_open_orders()`를 제공합니다.
- 현재 구현은 기존 `kis.wrapper` 함수들로 lazy 위임합니다.

## Import Boundary

KIS wrapper는 함수 호출 시점에 lazy-load합니다. 웹 서버와 텔레그램 명령이
`kis.wrapper`에 직접 의존하지 않도록 하는 전환 seam입니다.
