# Display (`display.py`)

이 모듈은 메인 터미널에서 알림 및 주문 상태를 표시하기 위한 단순화된 출력 시스템을 제공합니다.

## Purpose (목적)

**스크롤 기반 출력**을 제공하여 로그가 덮어쓰이지 않고 추적 가능하도록 합니다. ANSI 커서 제어가 제거되어 터미널 호환성이 향상되었습니다.

> **Note**: 실시간 시세 및 주문 모니터링은 별도의 **Event Viewer** (`event_viewer.py`)에서 Textual TUI로 처리됩니다.

## UI Design (UI 설계)

### Main Terminal (Scroll-based)
*   메뉴 및 사용자 입력은 일반적인 `print()`와 `input()`을 사용합니다.
*   알림은 `alert:[HH:MM:SS] 메시지` 형식으로 출력됩니다.
*   화면을 지우거나 커서를 이동하지 않습니다.

### Event Viewer (Textual TUI)
*   **Orders Panel**: 실시간 주문 목록
*   **Quotes Panel**: 종목별 최신 시세
*   **Log Panel**: MKT 이벤트 로그

## Functions (기능)

### get_fixed_width_name
문자열의 시각적 너비를 계산하고(한글 등 동아시아 문자는 2단위로 처리), 고정된 너비에 맞게 패딩하거나 자릅니다.

**Parameters**:
- `name` (str): 포맷할 문자열.
- `width` (int): 대상 시각적 너비 (기본값: 8).

**Returns**: 고정된 시각적 너비로 조정된 문자열.

### add_alert
```python
def add_alert(message: str, level: str = "INFO")
```
알림 메시지를 메인 터미널에 출력합니다.

**Parameters**:
- `message` (str): 알림 메시지.
- `level` (str): "INFO" (노랑), "SUCCESS" (초록), "ERROR" (빨강).

### update_order_state
```python
def update_order_state(order_id, ticker, name, side, price, qty, state, notify=True)
```
주문 정보를 Event Viewer로 전송합니다.

**Parameters**:
- `order_id` (str): 주문 번호.
- `ticker` (str): 종목 코드.
- `name` (str): 종목명.
- `side` (str): "Buy" 또는 "Sell".
- `price` (str): 주문 가격.
- `qty` (str): 수량.
- `state` (str): 주문 상태 (PLACED, EXECUTED 등).
- `notify` (bool): 메인 터미널에 알림 표시 여부.

**Effect**: Named Pipe를 통해 `ODR|...` 메시지를 Event Viewer로 전송합니다.

### remove_order_state
주문 제거 메시지를 Event Viewer로 전송합니다.

### clear_order_states
Event Viewer의 주문 목록을 초기화합니다 (`CLR|ORDERS`).

### show_in_result_area
```python
def show_in_result_area(lines: list[str])
```
여러 줄의 텍스트를 출력합니다 (스크롤 기반).

### input_at
```python
def input_at(row, col, prompt) -> str
```
사용자 입력을 받습니다. `row`, `col` 인자는 호환성을 위해 무시됩니다.

### render_ui / clear_result_area
호환성을 위한 no-op 함수입니다. 실제 작업은 수행하지 않습니다.

## Integration (통합)

*   **Event Viewer와 통신**: `kis.event_pipe.send_log(msg_type, message)`를 사용하여 Named Pipe로 메시지를 전송합니다.
*   **Message Types**:
    - `"ODR"`: 주문 정보
    - `"MKT"`: 시세 정보
    - `"CLR"`: 명령 (예: `ORDERS` 초기화)
