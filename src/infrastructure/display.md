# Display Adapter (`src/infrastructure/display.py`)

터미널 알림과 주문 상태를 출력하고, 사용할 수 있을 때만 `core.event_pipe`로
웹 이벤트 뷰어 메시지를 전달하는 인프라 어댑터입니다. 이벤트 파이프 연결 실패는
알림이나 주문 처리를 막지 않습니다.
