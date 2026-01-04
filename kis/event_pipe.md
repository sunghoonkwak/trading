# KIS Event Pipe (`kis/event_pipe.py`)

이 모듈은 Named Pipe 기반의 로깅 시스템을 처리하며, 메인 트레이딩 프로세스(서버)와 외부 Event Viewer(클라이언트) 간의 실시간 통신을 가능하게 합니다.

## Overview (개요)

모든 로깅 작업을 중앙 집중화하여, 표준 Python 로깅(파일/콘솔)과 분리된 뷰어를 위한 Named Pipe 출력을 동시에 처리합니다.

## Message Protocol (메시지 프로토콜)

### Message Types
*   **MKT**: Market Data (Quotes, Prices - displayed in Quotes & Log panels)
*   **ODR**: Order Notifications (Execution, Updates - displayed in Orders panel)
*   **SYS**: System Messages (Errors, PINGPONG - displayed in Log panel in Red)
*   **CLR**: Control Commands (e.g., clearing order list)

### Format
```
{msg_type}|{content}\n
```
예: `MKT|19:26:07|Apple Inc|AAPL|Bid:150.00|...\n`

## Key Components (주요 구성 요소)

### `PrintLevel` (IntEnum)
뷰어에 표시할 로그의 상세 레벨을 정의합니다:
*   `ERROR` (0): 치명적인 오류.
*   `INFO` (1): 일반적인 운영 이벤트 (주문, 시세 등).
*   `DEBUG` (2): 상세 디버깅 정보.

### Logging Functions

#### `print_viewer(msg_type, level, log)`
주요 로깅 인터페이스입니다.
*   `logging` 모듈을 통해 파일에 기록합니다.
*   `level <= print_log_level`인 경우 Named Pipe를 통해 뷰어로 전송합니다.

#### `send_log(msg_type, message)`
메시지를 Named Pipe로 전송합니다.
*   `msg_type|message\n` 형식으로 인코딩합니다.
*   Thread-safe하게 `_pipe_lock`을 사용합니다.

### Server-Side Functions (Main Process)
*   **`create_pipe_server()`**: Named Pipe를 초기화합니다.
*   **`wait_for_client()`**: 클라이언트가 연결될 때까지 대기(Block)합니다.
*   **`reset_pipe_server()`**: 연결 끊김 및 재연결 주기를 관리합니다.

### Client-Side Functions (Event Viewer)
*   **`connect_pipe_client()`**: 서버의 Named Pipe에 연결합니다.
*   **`receive_log(handle)`**: 파이프에서 들어오는 메시지를 읽기 위해 대기(Block)합니다.
    *   내부 버퍼를 사용하여 `\n`으로 메시지를 분리합니다.
    *   한 번에 하나의 완전한 메시지를 반환합니다.

## Concurrency (동시성)
*   `threading.Lock` (`_pipe_lock`)을 사용하여 여러 스레드(예: KIS Thread, Main Thread)에서 파이프에 동시에 쓰는 것을 안전하게 처리합니다.
