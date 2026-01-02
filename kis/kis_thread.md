# KIS Thread Module (`kis/kis_thread.py`)

이 모듈은 KIS API 통신을 전담하는 백그라운드 스레드를 구현합니다. 메인 UI의 블로킹을 방지하기 위해 별도 스레드에서 REST API 인증, WebSocket 연결, 데이터 요청을 처리합니다.

## Purpose (목적)
1.  **비동기 처리**: 네트워크 대기 시간이 발생하는 API 호출을 백그라운드에서 처리합니다.
2.  **연결 유지**: WebSocket 연결 및 재연결 로직을 관리합니다.
3.  **이벤트 파이프**: Event Viewer와 통신하기 위한 파이프 서버를 초기화합니다.

## Key Functions (주요 기능)

### Request Handling (요청 처리)
*   **`_handle_request(request)`**: `kis_request_queue`에서 요청을 꺼내 처리하고 결과를 `kis_response_queue`로 보냅니다.
    *   **KIS_AUTH/KIS_WS_AUTH**: REST 및 WebSocket 토큰 발급/갱신.
    *   **GET_PORTFOLIO**: (구현 예정) 백그라운드 포트폴리오 데이터 조회.

### WebSocket & Pipe (웹소켓 및 파이프)
*   **`initialize_websocket_and_pipe()`**: 모든 인증이 완료된 후 호출됩니다.
    *   WebSocket 클라이언트(`KISWebSocket`)를 생성하고 시작합니다.
    *   국내/해외 종목에 대한 실시간 시세 및 체결 통보를 구독합니다.
    *   `kis.event_pipe` 서버를 생성하여 외부 뷰어 연결을 대기합니다.

### Thread Management (스레드 관리)
*   **`start_kis_thread()`**: 스레드를 시작합니다 (`_kis_thread_loop`).
*   **`stop_kis_thread()`**: `threading.Event`를 사용하여 스레드를 안전하게 종료합니다.
*   **`_kis_thread_loop()`**: 스레드의 메인 루프로, 큐를 모니터링하며 요청을 처리합니다.

## Data Flow (데이터 흐름)
*   **Input**: `tuple(RequestType, args)` -> `kis_request_queue`
*   **Output**: `ThreadResponse` -> `kis_response_queue`
*   **Real-time Output**: `on_result` 콜백 -> `kis.event_pipe.print_viewer` -> Event Viewer

## Helper Functions (메인 스레드용)
*   `request_kis_auth()`: 인증 요청을 큐에 넣고 ID를 반환합니다.
*   `wait_for_response(req_id)`: 특정 요청에 대한 응답이 올 때까지 대기(Block)하거나 타임아웃 처리합니다.
