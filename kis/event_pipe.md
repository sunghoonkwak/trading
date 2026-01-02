# KIS Event Pipe (`kis/event_pipe.py`)

이 모듈은 Named Pipe 기반의 로깅 시스템을 처리하며, 메인 트레이딩 프로세스(서버)와 외부 Event Viewer(클라이언트) 간의 실시간 통신을 가능하게 합니다.

## Overview (개요)
모든 로깅 작업을 중앙 집중화하여, 표준 Python 로깅(파일/콘솔)과 분리된 뷰어를 위한 Named Pipe 출력을 동시에 처리합니다.

## Key Components (주요 구성 요소)

### `PrintLevel` (IntEnum)
뷰어에 표시할 로그의 상세 레벨을 정의합니다:
*   `ERROR` (0): 치명적인 오류.
*   `INFO` (1): 일반적인 운영 이벤트 (주문, 시세 등).
*   `DEBUG` (2): 상세 디버깅 정보.

### Logging Function
*   **`print_viewer(level, log)`**: 주요 로깅 인터페이스입니다.
    *   `logging` 모듈을 통해 파일에 기록합니다.
    *   `level <= print_log_level`인 경우 Named Pipe를 통해 뷰어로 전송합니다.

### Server-Side Functions (Main Process)
*   **`create_pipe_server()`**: Named Pipe를 초기화합니다.
*   **`wait_for_client()`**: 클라이언트가 연결될 때까지 대기(Block)합니다.
*   **`send_log(message)`**: 연결된 클라이언트에 문자열 메시지를 전송합니다.
*   **`reset_pipe_server()`**: 연결 끊김 및 재연결 주기를 관리합니다.

### Client-Side Functions (Event Viewer)
*   **`connect_pipe_client()`**: 서버의 Named Pipe에 연결합니다.
*   **`receive_log(handle)`**: 파이프에서 들어오는 메시지를 읽기 위해 대기(Block)합니다.

## Concurrency (동시성)
*   `threading.Lock` (`_pipe_lock`)을 사용하여 여러 스레드(예: KIS Thread, Main Thread)에서 파이프에 동시에 쓰는 것을 안전하게 처리합니다.
