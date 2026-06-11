# Order Admin (`src/broker/order_admin.py`)

이 모듈은 앱 소유 영역에서 미체결 주문 조회와 주문 관리 액션 런타임을
제공합니다.

## Responsibilities

- `fetch_open_orders()`를 제공합니다.
- `execute_manage_action(market, action_type, order_data, new_price=None)`를 제공합니다.
- `sync_open_orders()`를 제공합니다.
- 국내/해외 KIS 미체결 주문과 Toss OPEN 주문 조회 결과를 하나의
  DataFrame으로 합치고 `_market` 필드를 부여합니다.
- 주문 취소(`2`)와 정정(`1`) 요청을 공식 KIS endpoint wrapper 인자로
  변환합니다.
- `sync_open_orders()`는 조회 결과를 display state에 반영합니다.

## Import Boundary

공식 KIS auth와 endpoint wrapper, Toss 주문 조회 helper는 함수 호출
시점에 lazy-load합니다. 웹 서버와 텔레그램 명령은 `broker.order_admin`만
호출하고, 주문 관리 정책과 화면 동기화는 `src/kis/` 바깥의 앱 소유
영역에 둡니다.
