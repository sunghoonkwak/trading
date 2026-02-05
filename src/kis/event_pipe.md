# KIS Event Pipe (`kis/event_pipe.py`)

이 모듈은 IPC 기반의 로깅 시스템을 처리하며, 메인 트레이딩 프로세스(서버)와 외부 Event Viewer(클라이언트) 간의 실시간 통신을 가능하게 합니다.

## Overview (개요)

모든 로깅 작업을 중앙 집중화하여, 표준 Python 로깅(파일/콘솔)과 분리된 뷰어를 위한 IPC 출력을 동시에 처리합니다.

## Platform Support (플랫폼 지원)

**Windows와 Linux 모두 지원합니다:**

| Platform | IPC 방식 | 경로 |
|----------|----------|------|
| **Windows** | Named Pipe | `\\.\pipe\kis_websocket_log` |
| **Linux** | Unix Domain Socket | `/tmp/kis_websocket_log.sock` |

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

### Logging Levels
로그 레벨은 문자열로 정의됩니다:
*   `"ERROR"`: 치명적인 오류.
*   `"INFO"`: 일반적인 운영 이벤트 (주문, 시세 등).
*   `"DEBUG"`: 상세 디버깅 정보.

### Logging Functions

#### `print_viewer(msg_type, level, log)`
주요 로깅 인터페이스입니다.
*   `logging` 모듈을 통해 파일에 기록합니다.
*   `level`이 `"INFO"` 또는 `"ERROR"`인 경우 IPC를 통해 뷰어로 전송합니다.

#### `send_log(msg_type, message)`
메시지를 Write Queue에 추가합니다 (Non-blocking).
*   Queue가 가득 차면 오래된 메시지를 버리고 새 메시지를 추가합니다.
*   항상 최신 이벤트가 전달되도록 보장합니다.

### Async Write System (비동기 쓰기 시스템)

#### Write Queue
*   `WRITE_QUEUE_SIZE = 1000`: 최대 대기 메시지 수
*   Queue가 가득 차면 최대 100개의 오래된 메시지를 버립니다.

#### Platform-specific I/O
| Platform | 방식 |
|----------|------|
| **Windows** | Overlapped I/O (`FILE_FLAG_OVERLAPPED`) |
| **Linux** | Socket `sendall()` |

*   `WRITE_TIMEOUT_MS = 500`: 쓰기 타임아웃 (ms, Windows)
*   타임아웃 시 메시지를 버리고 writer thread가 blocking되지 않도록 합니다.

#### Writer Thread
*   **`start_writer_thread()`**: 백그라운드 writer thread를 시작합니다.
*   **`stop_writer_thread()`**: writer thread를 중지합니다.
*   Queue에서 메시지를 꺼내 `_do_write()`로 전송합니다.

#### Failure Recovery (실패 복구)
*   `MAX_CONSECUTIVE_FAILURES = 10`: 연속 쓰기 실패 임계치
*   연속 10회 쓰기 실패 시:
    1.  `_clear_queue()`: Queue의 모든 메시지를 비웁니다.
    2.  `_schedule_pipe_reset()`: 파이프/소켓을 리셋하고 재연결을 대기합니다.
*   Event Viewer가 응답하지 않아도 무한 루프에 빠지지 않고 자동 복구됩니다.

### IPC Lifecycle Management (Server-Side)
*   **`create_pipe_server()`**: Named Pipe (Windows) 또는 Unix Socket (Linux)을 초기화합니다.
*   **`wait_for_client()`**: 클라이언트가 연결될 때까지 대기합니다.
*   **`reset_pipe_server()`**: 연결 끊김 및 재연결 주기를 관리합니다.

### Client-Side Functions (Event Viewer)
*   **`connect_pipe_client()`**: 서버의 IPC에 연결합니다.
*   **`receive_log(handle)`**: IPC에서 들어오는 메시지를 읽기 위해 대기(Block)합니다.
    *   내부 버퍼를 사용하여 `\n`으로 메시지를 분리합니다.
    *   한 번에 하나의 완전한 메시지를 반환합니다.

## Concurrency (동시성)
*   `threading.Lock` (`_pipe_lock`)을 사용하여 여러 스레드(예: KIS Thread, Main Thread)에서 IPC에 동시에 쓰는 것을 안전하게 처리합니다.
*   Write Queue와 non-blocking I/O를 통해 Event Viewer가 느려져도 메인 프로그램이 blocking되지 않습니다.
