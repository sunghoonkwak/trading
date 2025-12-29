# event_pipe.md

Named Pipe를 이용한 프로세스 간 통신(IPC) 모듈입니다. 메인 프로세스(`main.py`)와 Event Viewer 프로세스(`event_viewer.py`) 간에 실시간 로그 데이터를 전송합니다.

## Purpose (목적)
Windows Named Pipe를 활용하여 WebSocket 로그를 별도 터미널로 전송하고, 메인 터미널의 UI를 깔끔하게 유지하는 것입니다.

## Configuration (설정)

### PIPE_NAME
- **Value**: `\\.\pipe\kis_websocket_log`
- **Description**: Named Pipe의 고유 식별자.

### PIPE_BUFFER_SIZE
- **Value**: `65536`
- **Description**: Pipe 버퍼 크기 (바이트).

## Function (기능)

### create_pipe_server
Named Pipe 서버를 생성합니다. `main.py` 시작 시 호출됩니다.
#### input
- `None`
#### output
- `bool`: 성공 여부.

### wait_for_client
클라이언트(Event Viewer) 연결을 대기합니다. 블로킹 호출입니다.
#### input
- `None`
#### output
- `bool`: 연결 성공 여부.

### send_log
Pipe를 통해 로그 메시지를 전송합니다. 논블로킹 호출입니다.
#### input
- `message` (str): 전송할 로그 메시지.
#### output
- `bool`: 전송 성공 여부.

### is_connected
클라이언트 연결 상태를 확인합니다.
#### input
- `None`
#### output
- `bool`: 연결 상태.

### connect_pipe_client
Pipe 서버에 연결합니다. `event_viewer.py`에서 호출됩니다.
#### input
- `None`
#### output
- `handle | None`: Pipe 핸들 또는 실패 시 None.

### receive_log
Pipe로부터 로그 메시지를 수신합니다. 블로킹 호출입니다.
#### input
- `handle`: Pipe 핸들.
#### output
- `str | None`: 수신된 메시지 또는 연결 끊김 시 None.

### close_pipe_server / close_pipe_client
Pipe 연결을 종료합니다.

### set_ui_callback
UI 새로고침 콜백 함수를 등록합니다. Pipe 재연결 시 호출됩니다.
#### input
- `callback` (callable): UI 새로고침 함수.
#### output
- `None`

### reset_pipe_server
Pipe 서버를 닫고 재생성하여 새 클라이언트 연결을 대기합니다. Viewer가 X버튼으로 종료된 후 재연결을 지원합니다.
#### input
- `ui_refresh_callback` (callable, optional): 재연결 후 호출할 UI 새로고침 함수.
#### output
- `None`
