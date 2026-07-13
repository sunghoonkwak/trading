# KIS Worker (`src/infrastructure/kis/worker.py`)

KIS 런타임 요청을 infrastructure 소유 큐/스레드에서 직렬 처리하는
worker입니다. KIS API adapter와 worker orchestration은 infrastructure에
있습니다.

## Core Logic

1. **스레드 루프**: `kis_request_queue`를 감시합니다. 인증 응답은 기존
   `kis_response_queue`에 넣고, portfolio read는 요청별 응답 queue로
   상관관계를 유지합니다.
2. **인증 요청**: REST/WebSocket 인증은
   `infrastructure.kis.rest_client.RESTClient`에 위임합니다.
   `KIS_ENABLE_REST_API=false`이면 REST 인증 요청은 disabled 응답을
   반환하지만 WebSocket 인증 요청은 계속 허용합니다.
3. **WebSocket 초기화**: `infrastructure.kis.ws_manager.WSManager`를
   호출해 KIS WebSocket 구독을 시작합니다. Event-pipe 연결 alert는
   composition root가 주입하는 best-effort publisher를 사용합니다.
4. **Portfolio read**: `WorkerSerializedKisOperations`는 read-only vendor
   callable을 직렬로 실행합니다. timeout 이후의 응답은 폐기하며, 동기
   vendor 호출을 강제 중단하거나 application service를 호출하지 않습니다.

## Key Functions

### `start_kis_thread` / `stop_kis_thread`

백그라운드 KIS worker 스레드를 시작하거나 안전하게 중지합니다.
`stop_kis_thread`는 worker loop를 멈추기 전에 `WSManager.stop()`을 호출해
WebSocket 재연결 루프도 함께 중지합니다. 이 경로는 Telegram `/system_off`
명령에서 사용됩니다.
