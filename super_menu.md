# Super Menu (`super_menu.py`)

이 모듈은 애플리케이션의 최상위 초기화 메뉴를 제공하며, 백그라운드 스레드의 시작 시퀀스를 관리합니다.

## Purpose (목적)
메인 트레이딩 메뉴로 진입하기 전의 진입점(Entry Point) 역할을 하며, 사용자가 KIS API 스레드와 텔레그램 봇 스레드를 독립적으로 초기화할 수 있도록 합니다.

## Key Functions (주요 기능)

### Menu Rendering
*   **`super_menu()`**: 메인 루프입니다. KIS 및 텔레그램 스레드의 현재 상태를 표시하고 사용자 입력을 받습니다.
*   **`_render_super_menu()`**: 화면을 지우고 `display.show_in_result_area`를 사용하여 메뉴 UI를 그립니다. 또한 알림 프로세서를 트리거하여 로그를 표시합니다.
*   **`_build_menu_lines()`**: 준비 상태에 따라 상태 아이콘(실행 중/중지됨/에러)과 사용 가능한 옵션을 동적으로 구성하여 메뉴 텍스트를 생성합니다.

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

## Data Flow (데이터 흐름)
*   `thread_state`와 상호 작용하여 전역 스레드 상태를 읽고 씁니다.
*   `display` 모듈을 사용하여 UI 렌더링 및 알림(`add_alert`)을 처리합니다.
*   `kis_thread` 함수를 호출하여 백그라운드 작업을 트리거합니다.
