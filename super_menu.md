# Super Menu (`super_menu.py`)

이 모듈은 애플리케이션의 최상위 초기화 메뉴를 제공하며, 백그라운드 스레드의 시작 시퀀스를 관리합니다.

## Purpose (목적)

메인 트레이딩 메뉴로 진입하기 전의 진입점(Entry Point) 역할을 하며, 사용자가 KIS API 스레드와 텔레그램 봇 스레드를 독립적으로 초기화할 수 있도록 합니다.

## Design (설계)

### Scroll-based Output
*   ANSI 커서 제어 없이 일반 `print()`를 사용하는 스크롤 기반 메뉴입니다.
*   화면을 지우거나 덮어쓰지 않아 로그 추적이 용이합니다.

### Startup Sequence
`main.py`에서 호출 시 다음 순서로 자동 시작됩니다:
1. **Telegram 초기화**: 알림 수신을 위해 먼저 시작
2. **Event Viewer 실행**: 별도 터미널에서 Textual TUI 뷰어 자동 실행
3. **Super Menu 표시**: 사용자 상호작용 시작

## Menu Options (메뉴 옵션)

| Key | Action |
|-----|--------|
| `1` | Telegram Bot 초기화 |
| `2` | KIS API 스레드 초기화 |
| `3` | 트레이딩 메뉴 진입 (KIS 인증 필요) |
| `t` | 테스트: Event Viewer에 더미 데이터 전송 |
| `q` | 종료 |

## Key Functions (주요 기능)

### Menu Rendering
*   **`super_menu()`**: 메인 루프입니다. KIS 및 텔레그램 스레드의 현재 상태를 표시하고 사용자 입력을 받습니다.
*   **`_print_super_menu()`**: 현재 스레드 상태와 메뉴 옵션을 출력합니다.

### Initialization Logic (초기화 로직)
*   **`_init_kis_thread()`**:
    1.  `start_kis_thread()`를 통해 KIS 백그라운드 스레드를 시작합니다.
    2.  REST API 인증을 요청합니다.
    3.  WebSocket 인증을 요청합니다.
    4.  `initialize_websocket_and_pipe()`를 통해 WebSocket 구독 및 Event Pipe 서버를 초기화합니다.
*   **`_init_telegram_thread()`**:
    1.  텔레그램 스레드 상태를 `STARTING`으로 설정합니다.
    2.  `telegram_bot.initialize_telegram()`을 호출하여 봇을 시작합니다.
    3.  성공 시 상태를 `RUNNING`으로, 실패 시 `ERROR`로 업데이트합니다.

### Test Function (테스트 기능)
*   **`_send_dummy_data()`**: Event Viewer 테스트용 더미 데이터를 전송합니다.
    *   `CLR|ORDERS`: 주문 목록 초기화
    *   `ODR|...`: 샘플 주문 3건
    *   `MKT|...`: 샘플 시세 2건

### Shutdown (종료)
*   KIS 스레드 정지
*   Telegram 봇 종료
*   Event Viewer 종료 (`close_viewer()`)

### 3. Safety Guards (안전 장치)
*   **Duplicate Execution Prevention**:
    *   Telegram/KIS Init 메뉴 선택 시, 이미 실행 중이면 경고 메시지만 출력하고 중복 실행을 차단합니다.
    *   KIS Init의 경우, **Physical Thread Check**를 먼저 수행하여 스레드가 죽어있을 경우 즉시 재시작하도록 로직 순서를 최적화했습니다.
*   **Status Check**: 각 메뉴 실행 전 필요한 전제 조건(KIS Ready 등)을 체크합니다.

## Data Flow (데이터 흐름)
*   `thread_state`와 상호 작용하여 전역 스레드 상태를 읽고 씁니다.
*   `display.add_alert()`를 사용하여 알림을 메인 터미널에 표시합니다.
*   `event_pipe.send_log()`를 사용하여 Event Viewer에 데이터를 전송합니다.
