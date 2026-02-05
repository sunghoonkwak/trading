# Thread State Management (`thread_state.py`)

이 모듈은 애플리케이션 내 모든 스레드의 수명 주기(Lifecycle) 상태와 공유 상태를 관리하며, 스레드 안전(Thread-Safe)한 접근과 수정을 보장합니다.

## Purpose (목적)
KIS 스레드(REST API, WebSocket)와 텔레그램 스레드의 현재 상태를 중앙에서 관리하는 저장소 역할을 합니다. `threading.Lock`을 사용하여 동시성 문제(Race Condition)를 방지합니다.

## Key Components (주요 구성 요소)

### Enums
*   **`ThreadStatus`**: 스레드 생명 주기 상태 (`NOT_STARTED`, `STARTING`, `RUNNING`, `ERROR`, `STOPPED`).
*   **`AuthStatus`**: 인증 상태 (`NOT_AUTHENTICATED`, `AUTHENTICATING`, `AUTHENTICATED`, `FAILED`, `EXPIRED`).
*   **`WebSocketStatus`**: 웹소켓 연결 상태 (`DISCONNECTED`, `CONNECTING`, `CONNECTED`, `ERROR`).

### State Containers (상태 컨테이너)
*   **`KISThreadState`**:
    *   관리 항목: `thread_status`, `auth_status` (REST), `ws_auth_status` (WebSocket), `ws_status` (연결), `last_error`.
*   **`TelegramThreadState`**:
    *   관리 항목: `thread_status`, `bot_connected` (봇 연결 여부), `last_error`.

### Thread-Safe Accessors (접근자)
전역 인스턴스인 `kis_state`와 `telegram_state`는 `_state_lock`으로 보호됩니다.

*   **읽기 (Read)**: `get_kis_state()`, `get_telegram_state()`
*   **쓰기 (Write)**: `update_kis_state(**kwargs)`, `update_telegram_state(**kwargs)`

### Helper Functions
*   `is_kis_ready()`: KIS 스레드가 실행 중(`RUNNING`)이고 인증(`AUTHENTICATED`)되었는지 확인.
*   `is_telegram_ready()`: 텔레그램 봇이 실행 중(`RUNNING`)이고 연결(`bot_connected`)되었는지 확인.
*   `get_status_summary()`: UI 표시를 위해 모든 스레드의 상태를 딕셔너리 형태로 반환.
