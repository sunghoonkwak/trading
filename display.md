# Display Module (`display.py`)

## 개요
터미널 출력과 시스템 알림을 처리하는 모듈입니다.
웹 기반 Event Viewer 도입으로 인해 역할이 축소 및 변경되었습니다.

## 주요 기능

### `add_alert(message, level="INFO")`
시스템 알림을 발생시킵니다.
1. **Log File**: `WebSocket_latest.log`에 즉시 기록합니다.
2. **Web Viewer**: `kis.event_pipe`가 연결되어 있다면 `ALT` 메시지를 전송하여 웹 대시보드 System Log에 표시합니다.
3. **Terminal Output**:
   - 모든 알림 메시지는 터미널에도 컬러 텍스트로 **항상 출력**됩니다.
   - Web Viewer 및 로그 파일에도 동일하게 기록됩니다.

### `update_order_state(...)`
주문 상태 변경 시 호출됩니다.
- 변경 내역을 `kis.event_pipe`를 통해 웹 뷰어로 전송합니다 (`ODR` 메시지).
- 터미널에는 별도로 출력하지 않습니다 (웹 뷰어 확인 권장).

### `clear_quotes()`
웹 뷰어의 시세(Quote) 목록을 초기화하라는 신호를 보냅니다 (`CLR` 메시지).
