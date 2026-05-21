# KIS Event Handler (`kis/event_handler.py`)

이 모듈은 KIS WebSocket으로부터 수신된 실시간 데이터를 처리하는 로직을 포함합니다.

## Purpose (목적)
원래 `main.py`에 있던 로직을 분리하여 다음과 같은 목적을 달성했습니다:
1.  **순환 참조 해결 (Resolve Circular Dependencies)**: 이벤트 처리 로직을 메인 애플리케이션 진입점과 분리합니다.
2.  **모듈화 개선 (Improve Modularity)**: KIS 데이터 포맷 파싱을 위한 구체적인 로직을 캡슐화합니다.

## Key Function (주요 기능)

### `on_result(ws, tr_id, df, dm)`
KIS WebSocket 클라이언트가 메시지를 수신할 때마다 실행되는 콜백 함수입니다.

#### Parameters:
*   `ws`: WebSocket 인스턴스.
*   `tr_id`: 트랜잭션 ID (예: 호가 `H0UNASP0`, 체결 `H0STCNI0`).
*   `df`: 파싱된 데이터를 담은 Pandas DataFrame (해당되는 경우).
*   `dm`: Raw 데이터 딕셔너리 (해당되는 경우).

#### Responsibilities (역할):
1.  **Market Data (시세 데이터 - `H0UNASP0`, `H0UNCNT0`, 등)**:
    *   호가(Ask/Bid) 및 현재가(Price) 업데이트를 파싱합니다.
    *   **Data Validation**: 손상된 패킷이나 비정상적인 값(비정상적으로 긴 종목 코드 등)을 감지하고 필터링합니다.
    *   `MarketStateManager.update_ticker()` 경로로 시세 상태를 업데이트합니다.
    *   첫 시세 수신 시 `MarketStateManager`의 주기 저장 루프가 시작됩니다.
    *   `event_pipe`를 통해 Event Viewer로 로그를 포맷팅하여 전송합니다.

2.  **Order Execution/Modifications (주문 체결/정정 - `H0STCNI0`, `H0GSCNI0`)**:
    *   체결 통보(접수, 정정, 취소, 체결, 거부)를 파싱합니다.
    *   상세 체결 정보를 로그로 남깁니다.
    *   **전체 데이터 덤프**: 모든 주문 알림(ODR/EXE/CAN/REJ 등)에 대해 WebSocket 메시지 전체 내용을 **`INFO`** 레벨로 기록하여, 주문 거절 원인 등을 분석할 수 있도록 합니다.
    *   메인 UI에 `add_alert`를 보냅니다.
    *   **Telegram 알림**: 체결 완료 시 `send_notification()`을 호출하여 원격 알림 전송.
    *   `request_sync()`를 호출하여 주문 동기화를 자동 트리거합니다 (디바운싱 적용).

3.  **System Messages (시스템 메시지)**:
    *   연결 유지를 위한 PINGPONG 메시지를 처리합니다 (시스템 로깅 타임스탬프 사용).

## Dependencies (의존성)
*   **`kis.event_pipe`**: 외부 뷰어로 로그를 스트리밍하는 데 사용됩니다.
*   **`trading_state`**: 검증, 락, 주기 저장을 포함한 시세 상태 업데이트를 담당합니다.
*   **`display`**: UI 알림을 표시합니다.
*   **`telegram_bot.telegram_utils`**: 주문 체결 시 Telegram 알림을 전송합니다.

## MKT 메시지 형식
Event Viewer로 전송되는 시세 데이터 형식:
```
Name|Ticker|Bid|Last(Vol)|Diff(Rate%)|Ask
```
- 시간(time)과 레이블(Bid:, Last:, Diff:, Ask:)이 제거된 간결한 형식
- 시간은 WebSocket 메시지의 `time` 필드로 별도 전송
