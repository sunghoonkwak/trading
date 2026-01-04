# Main Application (`main.py`)

이 파일은 트레이딩 애플리케이션의 진입점(Entry Point)입니다.

## Responsibilities (역할)
애플리케이션의 역할이 단순화되어 고수준의 관리자(Orchestrator) 역할을 수행합니다:
1.  **Environment Setup (환경 설정)**:
    *   스레드 안전성 문제를 방지하기 위해 `requests_cache`를 비활성화합니다.
    *   메인 `asyncio` 이벤트 루프를 설정합니다.
2.  **Automated Startup Sequence (자동 시작 시퀀스)**:
    *   **Step 1**: Telegram 봇 초기화 (알림 수신 준비)
    *   **Step 2**: Event Viewer를 새 터미널 창에서 자동 실행
    *   **Step 3**: Super Menu 표시
3.  **Super Menu Delegation (위임)**:
    *   `super_menu.super_menu()`를 호출하여 스레드 초기화(KIS, Telegram) 및 사용자 상호 작용을 처리합니다.

## Logic Flow (로직 흐름)
1.  **Startup**:
    *   `main()`이 호출됩니다.
    *   Telegram 봇이 먼저 초기화됩니다.
    *   `event_viewer.spawn_viewer()`가 Event Viewer를 실행합니다.
    *   `super_menu()`로 제어권이 넘어갑니다.
2.  **Menu Loop**:
    *   제어권이 `super_menu()`로 넘어가며, 종료 시까지 애플리케이션 수명 주기를 관리합니다.
3.  **Concurrency (동시성)**:
    *   `main.py`는 **Main Thread**를 실행하며, UI 루프와 텔레그램 봇 처리를 담당합니다.
    *   백그라운드 스레드(KIS Thread)는 `super_menu`와 `kis_thread`에 의해 생성 및 관리됩니다.

## Key Changes (리팩토링 변경 사항)
*   **Automatic Startup**: Telegram → Event Viewer → Super Menu 순서로 자동 시작
*   **Event Handling**: `on_result` 로직이 `kis/event_handler.py`로 이동되었습니다.
*   **Logging**: 직접적인 로깅 정의가 제거되고 `kis.event_pipe`를 사용하도록 변경되었습니다.
