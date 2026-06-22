# Order Admin (`src/broker/order_admin.py`)

이 모듈은 앱 소유 영역에서 미체결 주문 조회와 주문 관리 액션 런타임을
제공합니다.

## Responsibilities

- `fetch_open_orders()`를 제공합니다.
- `execute_manage_action(market, action_type, order_data, new_price=None)`를 제공합니다.
- `sync_open_orders()`를 제공합니다.
- 해외 KIS 미체결 주문과 Toss OPEN 주문 조회 결과를 하나의 DataFrame으로
  합치고 `_market` 필드를 부여합니다.
- 런타임 환경변수 `KIS_ENABLE_REST_API=false`이면 KIS 미체결 조회/취소/
  정정을 건너뜁니다. Toss OPEN 조회와 Toss 취소는 계속 허용됩니다.
- KIS 국내 주문 조회/관리는 기본 비활성화되어 있습니다. 국내 주문을
  다시 관리하려면 런타임 환경변수 `KIS_ENABLE_DOMESTIC=true`를 설정합니다.
- 주문 취소(`2`)와 정정(`1`) 요청을 공식 KIS endpoint wrapper 인자로
  변환합니다.
- `sync_open_orders()`는 조회 결과를 display state에 반영합니다.

## Import Boundary

공식 KIS auth와 endpoint wrapper, Toss 주문 조회 helper는 함수 호출
시점에 lazy-load합니다. 웹 서버와 텔레그램 명령은 `broker.order_admin`만
호출하고, 주문 관리 정책과 화면 동기화는 `src/kis/` 바깥의 앱 소유
영역에 둡니다.
