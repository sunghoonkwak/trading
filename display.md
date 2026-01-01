# display.md

이 모듈은 ANSI 이스케이프 코드를 사용하여 터미널 기반의 사용자 인터페이스(UI)와 컬러 로그 시스템을 처리합니다. 로그 관리와 사용자 입력을 분리하여 중단 없는 실시간 모니터링 환경을 제공합니다.

## Purpose (목적)
명령줄 인터페이스의 가독성을 유지하면서, 실시간 주가 시세, 주문 상태 및 시스템 메시지를 시각적으로 구조화하여 제공하는 것입니다.

## UI Layout (화면 구성)

```
Row 1-3:     Main Header (제목, 로그 레벨, 지수)
Row 4-11:    Menu Options (1-3, r, p, c, q - 총 8줄)
Row 12:      -------- (구분선)
Row 13:      Enter Choice: (입력 영역)
Row 14:      -------- (구분선)
Row 15:      -------------------------- Orders -------------------------- (주문 구분선)
Row 16-25:   Order List (실시간 미체결 주문 목록, 최대 10개)
Row 26:      -------------------------- Alerts -------------------------- (알림 구분선)
Row 27+:     Alerts Log (최신 알림 메시지, 최대 15개)
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

### get_fear_and_greed_display
Fear & Greed 지수를 안전하게 가져옵니다. 10분 캐싱을 적용하여 UI 블로킹을 방지합니다.
#### input
- `None`.
#### output
- `int` or `str`: 현재 지수 값 (0~100) 또는 초기화/에러 상태 문자열.

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
- `ticker` (str): 종목 코드.
- `name` (str): 종목명.
- `side` (str): "BUY" 또는 "SELL".
- `price` (str): 주문 가격.
- `qty` (str): 수량.
#### output
- `None`.

### add_alert
```python
def add_alert(message: str, level: str = "INFO")
```
알림 메시지를 화면 하단 알림 영역에 표시합니다.
- **Thread-safe**: 모든 모듈 및 백그라운드 스레드(Telegram 등)에서 직접 호출할 수 있습니다.
- 메시지는 내부 큐(`_pending_alerts`)를 거쳐 메인 루프에서 안전하게 화면에 렌더링됩니다.
- `level`: "INFO" (기본), "SUCCESS" (초록), "ERROR" (빨강), "WARN" (노랑)
#### input
- `message` (str): 알림 메시지.
- `level` (str): "INFO", "ERROR", "SUCCESS".
#### output
- `None`.

### process_pending_alerts
큐에 쌓인 알람을 처리하여 `alert_buffer`에 추가합니다.
#### output
- `bool`: 처리된 알람이 있으면 True.

### start_alert_processor
백그라운드에서 500ms마다 큐를 체크하고 UI를 갱신하는 스레드를 시작합니다. 메뉴 시작 시 호출됩니다.

### clear_order_states
미체결 주문 목록 데이터만 초기화합니다. 새로운 동기화 작업을 시작하기 전에 호출됩니다.
#### input
- `None`.
#### output
- `None`.

### remove_order_state
특정 주문 고유 번호(odno)를 사용하여 미체결 주문 목록에서 해당 항목을 즉시 제거합니다. WebSocket 체결/취소 통지 시 API 동기화 전 UI를 선제적으로 갱신하기 위해 사용됩니다.
#### input
- `odno` (str): 제거할 주문 번호.
#### output
- `None`.

### clear_all_display_data
주문 목록과 알림 버퍼를 모두 초기화하고 화면을 갱신합니다.
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

