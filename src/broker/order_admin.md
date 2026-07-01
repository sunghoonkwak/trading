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
  Event Viewer의 주문 시간은 조회 시각이 아니라 브로커 응답의 주문
  입력 시각을 사용합니다. KIS는 `ord_tmd`, Toss는 `orderedAt`을
  `HH:MM:SS`로 변환합니다.

## Market-Specific Behavior

- `_market="TOSS"`: Toss OPEN 주문입니다. Toss 정정은 지원하지 않고
  취소만 Toss cancel endpoint로 보냅니다.
- `_market="KR"`: KIS 국내 주문입니다. `KIS_ENABLE_DOMESTIC=true`일
  때만 조회/관리하며 국내 KIS 정정/취소 endpoint 인자로 변환합니다.
- 그 외 `_market` 값은 KIS 해외 주문으로 취급합니다. 현재 조회 경로는
  해외 KIS 미체결 주문에 `_market="US"`를 부여합니다.

화면 표시용 주문 값(`side`, `price`, `qty`, `time_str`)과 주문 관리
액션은 공통 진입 함수에서 `market`으로 분기한 뒤 Toss, KIS 국내,
KIS 해외 helper에서 각각 변환합니다. Toss는 국내/해외 시장 구분이
아니라 Toss 브로커 주문으로 다룹니다.

## Import Boundary

공식 KIS auth와 endpoint wrapper, Toss 주문 조회 helper는 함수 호출
시점에 lazy-load합니다. 웹 서버와 텔레그램 명령은 `broker.order_admin`만
호출하고, 주문 관리 정책과 화면 동기화는 `src/kis/` 바깥의 앱 소유
영역에 둡니다.
