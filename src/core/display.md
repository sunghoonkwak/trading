# Display Module (`src/core/display.py`)

## Overview (개요)
터미널 출력과 시스템 알림을 처리하는 모듈입니다. `src/core/` 패키지에 위치하여 매매 시스템의 시각적 피드백과 로그 출력을 담당합니다.
웹 기반 Event Viewer 도입으로 인해 역할이 축소 및 변경되었습니다.
`core.event_pipe` 모듈을 **Lazy Import**하여 초기화 시점의 의존성 문제를 해결했습니다.

## Key Functions (주요 함수)

### `add_alert(message, level="INFO", time_str=None)`
시스템 알림을 발생시킵니다.
1. **Log File**: 로그 매니저를 통해 설정된 로그 파일에 즉시 기록합니다.
2. **Web Viewer**: `core.event_pipe`가 연결되어 있다면 `ALT` 메시지를 전송하여 웹 대시보드 알림 로그에 표시합니다.
    - `time_str`이 제공되면 해당 시간을 사용하고, 그렇지 않으면 현재 시간을 사용합니다.
3. **Terminal Output**:
   - 모든 알림 메시지는 터미널에도 컬러 텍스트로 **항상 출력**됩니다.
   - `event_pipe` 연결 여부와 관계없이 터미널 출력은 보장됩니다.

### `update_order_state(..., time_str=None)`
주문 상태 변경 시 호출됩니다.
- 변경 내역을 `core.event_pipe`를 통해 웹 뷰어로 전송합니다 (`ODR` 메시지).
- 주문 메시지는 `name|ticker|side|qty|broker|price|state|order_id`
  순서이며, 웹 뷰어는 수량 다음에 `KIS` 또는 `TOSS`를 표시합니다.
- `time_str` 파라미터를 통해 주문의 실제 체결 시간을 전달할 수 있습니다.
- `notify=True`이면 동일 내용을 `add_alert()`로도 남기며, `notify=False`이면 웹 뷰어 상태만 갱신합니다.

### `clear_quotes()`
웹 뷰어의 시세(Quote) 목록을 초기화하라는 신호를 보냅니다 (`CLR` 메시지).
