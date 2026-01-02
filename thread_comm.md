# Thread Communication Module (`thread_comm.py`)

이 모듈은 메인 스레드와 백그라운드 스레드(KIS 스레드, 텔레그램 스레드) 간의 안전하고 구조화된 통신을 위한 인프라를 정의합니다.

## Purpose (목적)
Python의 `queue.Queue`를 사용하여 스레드 간 안전한 메시지 전달을 보장하고, `dataclasses`를 활용하여 요청/응답 객체를 구조화합니다.

## Key Components (주요 구성 요소)

### Data Classes
*   **`RequestType` (Enum)**: 지원되는 요청 유형을 정의합니다 (예: `KIS_AUTH`, `GET_PORTFOLIO`).
*   **`ThreadRequest`**:
    *   스레드로 전송되는 함수 호출 정보를 담는 컨테이너입니다.
    *   필드: `request_type`, `func_name`, `args`, `kwargs`, `request_id`, `timestamp`.
*   **`ThreadResponse`**:
    *   스레드로부터 반환되는 결과 정보를 담는 컨테이너입니다.
    *   필드: `request_id`, `success`, `result`, `error`, `timestamp`.

### Global Queues (전역 큐)
1.  **KIS Thread**
    *   `kis_request_queue`: KIS 스레드**로** 보내는 요청 큐.
    *   `kis_response_queue`: KIS 스레드**로부터** 받는 응답 큐.
    *   `kis_status_queue`: KIS 스레드의 상태 업데이트(인증, 연결 상태 등) 큐.
2.  **Data Flow**
    *   `data_queue`: KIS 스레드에서 메인 스레드로 전달되는 실시간 WebSocket 데이터 패킷 스트림.
3.  **Telegram Thread**
    *   `telegram_request_queue`: 텔레그램 스레드**로** 보내는 요청 큐 (Main을 경유).
    *   `telegram_response_queue`: 텔레그램 스레드**로부터** 받는 응답 큐.

## Usage Pattern (사용 패턴)
1.  **요청 전송 (Sending a Request)**:
    ```python
    req = ThreadRequest(type=RequestType.KIS_AUTH)
    kis_request_queue.put(req)
    ```
2.  **처리 (Processing in Thread)**:
    ```python
    req = kis_request_queue.get()
    # ... 작업 처리 ...
    resp = ThreadResponse(request_id=req.request_id, success=True)
    kis_response_queue.put(resp)
    ```
3.  **응답 수신 (Receiving Response)**:
    ```python
    resp = kis_response_queue.get()
    if resp.success:
        print(resp.result)
    ```
