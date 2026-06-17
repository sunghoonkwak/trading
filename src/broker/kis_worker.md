# KIS Worker (`src/broker/kis_worker.py`)

KIS 런타임 요청을 앱 소유 큐/스레드에서 직렬 처리하는 worker입니다.
`src/kis/`는 KIS API 어댑터만 소유하고, 스레드 orchestration과
포트폴리오 통합 요청은 broker/data 경계에서 조율합니다.

## Core Logic

1. **스레드 루프**: `kis_request_queue`를 감시하고 요청별 응답을
   `kis_response_queue`에 넣습니다.
2. **인증 요청**: REST/WebSocket 인증은 `broker.kis_rest_client.RESTClient`에
   위임합니다.
3. **포트폴리오 요청**: `data.portfolio_integration`에서 KIS/GSheet
   통합 raw 포트폴리오를 조회합니다.
4. **WebSocket 초기화**: `broker.kis_ws_manager.WSManager`를 호출해 KIS
   WebSocket 구독을 시작합니다.

## Key Functions

### `start_kis_thread` / `stop_kis_thread`

백그라운드 KIS worker 스레드를 시작하거나 안전하게 중지합니다.

### `request_portfolio`

포트폴리오 조회 요청을 큐에 등록합니다. `scope`는 `all`, `kis`, `toss`
중 하나이며 data 통합 계층이 해당 scope에 맞는 source만 조회합니다.

### `wait_for_response`

특정 요청 ID에 대한 응답이 올 때까지 응답 큐를 폴링합니다.
