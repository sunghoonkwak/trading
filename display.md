# display.md

이 모듈은 ANSI 이스케이프 코드를 사용하여 터미널 기반의 사용자 인터페이스(UI)와 컬러 로그 시스템을 처리합니다. 로그 관리와 사용자 입력을 분리하여 중단 없는 실시간 모니터링 환경을 제공합니다.

## Purpose (목적)
명령줄 인터페이스의 가독성을 유지하면서, 실시간 주가 시세, 주문 상태 및 시스템 메시지를 시각적으로 구조화하여 제공하는 것입니다.

## UI Layout (화면 구성)

```
Row 1-3:   Header (시스템 제목, VIEWER 상태)
Row 4-11:  Menu (8줄, 확장됨)
Row 12:    ========
Row 13:    Order Status & Alerts
Row 14:    --------
Row 15+:   주문 목록 + 알림
```

## Function (기능)

### get_fixed_width_name
문자열의 시각적 너비를 계산하고(한글 등 동아시아 문자는 2단위로 처리), 고정된 너비에 맞게 패딩하거나 자릅니다.
#### input
- `name` (str): 포맷할 문자열.
- `width` (int): 대상 시각적 너비 (기본값: 8).
#### output
- `str`: 고정된 시각적 너비로 조정된 문자열.

### get_ansi_rgb
특정 종목 티커에 할당된 RGB 색상을 조회하여 제공된 텍스트를 ANSI 컬러 코드로 감쌉니다.
#### input
- `code` (str): 주식 티커 심볼.
- `text` (str): 색상을 적용할 텍스트.
#### output
- `str`: 색상이 적용된 텍스트 또는 설정이 없을 경우 원본 텍스트.

### send_to_viewer
Named Pipe를 통해 로그를 별도 터미널(Event Viewer)로 전송합니다.
#### input
- `log` (str): 전송할 로그 메시지.
#### output
- `None`.

### print_log
로그 메시지를 파일에 기록하고 Named Pipe를 통해 Event Viewer로 전송합니다.
#### input
- `level` (PrintLevel): 로그 레벨 (ERROR, INFO, DEBUG).
- `log` (str): 로그 메시지 내용.
#### output
- `None`.

### update_order_state
주문 상태를 메인 터미널에 표시하기 위해 업데이트합니다.
#### input
- `order_id` (str): 주문 번호.
- `ticker` (str): 종목 코드.
- `name` (str): 종목명.
- `side` (str): "BUY" 또는 "SELL".
- `price` (str): 주문 가격.
- `qty` (str): 수량.
- `state` (str): 주문 상태 (PLACED, EXECUTED, CANCELED, CORRECTING).
#### output
- `None`.

### add_alert
메인 터미널의 알림 영역에 메시지를 추가합니다.
#### input
- `message` (str): 알림 메시지.
- `level` (str): "INFO", "ERROR", "SUCCESS".
#### output
- `None`.

### clear_completed_orders
EXECUTED 및 CANCELED 상태의 주문을 화면에서 제거합니다.
#### input
- `None`.
#### output
- `None`.

### render_ui
제목, 메뉴 옵션, 주문 상태 및 알림을 포함한 전체 터미널 인터페이스를 렌더링합니다.
#### input
- `full_refresh` (bool): 정적 요소를 다시 그릴지 여부.
#### output
- `None`.

### show_in_result_area
터미널의 지정된 "결과 영역"(1~10행)에 문자열 목록을 표시합니다.
#### input
- `lines` (list[str]): 표시할 텍스트 줄 목록.
#### output
- `None`.

### input_at
터미널의 지정된 행/열 위치에서 사용자 입력을 받습니다.
#### input
- `row` (int): 행 번호.
- `col` (int): 열 번호.
- `prompt` (str): 표시할 프롬프트 메시지.
#### output
- `str`: 사용자가 입력한 문자열.

### prepare_exit
종료 시 커서를 터미널 하단으로 이동하여 UI가 셸 프롬프트에 의해 덮어쓰이지 않도록 합니다.

