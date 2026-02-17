# KIS Thread (`src/kis/kis_thread.py`)

KIS API와의 모든 상호작용을 비동기적으로 처리하기 위한 전용 스레드 모듈입니다.
메인 스레드와의 큐(Queue) 통신을 통해 REST 요청을 처리하고 WebSocket 상태를 조율합니다.

# Core Logic (핵심 로직)

1. **스레드 루프**: 메인 스레드에서 보낸 요청 큐(`kis_request_queue`)를 감시하며 무한 루프를 돕니다.
2. **요청 처리**: `RESTClient`를 호출하여 실제 API 작업을 수행하고 결과를 응답 큐(`kis_response_queue`)에 넣습니다.
3. **컴포넌트 조율**: `WSManager`의 초기화 및 생명주기를 관리합니다.
4. **상태 관리**: `state.system_state`를 통해 스레드 및 네트워크 상태를 전역적으로 업데이트합니다.

# Key Functions (주요 함수)

## `start_kis_thread` / `stop_kis_thread`
백그라운드 스레드를 시작하거나 안전하게 중지합니다.

## `initialize_websocket_and_pipe`
`WSManager`를 통해 실시간 시세 수신을 시작합니다.

## `wait_for_response`
특정 요청 ID에 대한 응답이 올 때까지 큐를 폴링하며 대기합니다. (동기식 호출을 위한 래퍼)

## `request_portfolio`
포트폴리오 조회 요청을 큐에 등록합니다. `kis_only=True` 시 GSheet을 건너뛰어 KIS 데이터만 조회합니다.

# Configuration (None)

# Usage Example (사용 예시)

```python
from kis.kis_thread import start_kis_thread, request_portfolio, wait_for_response

# 1. 스레드 시작
start_kis_thread()

# 2. 비동기 요청 후 대기
req_id = request_portfolio()
response = wait_for_response(req_id)
```
