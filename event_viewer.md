# Event Viewer (`event_viewer.py`)

이 모듈은 메인 프로그램으로부터 Named Pipe를 통해 수신한 실시간 시세 데이터와 로그를 표시하는 독립 실행형 터미널 애플리케이션입니다.

## Overview (개요)
`kis.event_pipe` 서버에 연결하여 다음과 같은 특화된 TUI(Text User Interface)를 렌더링합니다:
1.  **Sticky Header (고정 영역)**: 각 종목의 최신 가격/주문 정보를 상단에 고정하여 표시합니다.
2.  **Scrolling History (스크롤 영역)**: 고정 영역 하단에 모든 이벤트의 시간순 로그를 표시합니다.

## Key Features (주요 기능)

### Process Detection (프로세스 감지)
*   **Windows Named Mutex**: `StevenOpenAPITradingViewer`라는 이름의 뮤텍스(Mutex)를 사용하여 뷰어의 실행 여부를 시스템 전역에서 확실하게 감지합니다.
*   **`acquire_mutex()`**: 뷰어 시작 시 뮤텍스를 생성하여 실행 중임을 알립니다.
*   **`is_running()`**: 메인 프로그램은 이 뮤텍스의 존재 여부를 통해 뷰어 프로세스가 실제로 살아있는지 확인합니다. (이전의 불완전한 `subprocess` 추적 방식 대체)

### Split View Interface (분할 화면)
*   **Sticky Area**: ANSI 이스케이프 코드를 사용하여 터미널 상단의 특정 라인을 덮어씀으로써, 활성 종목을 위한 "대시보드" 느낌을 제공합니다.
*   **History Area**: 화면 하단에 스크롤 영역(ANSI `DECSTBM`)을 설정하여, 헤더를 방해하지 않고 과거 이벤트를 기록합니다.

### Data Processing (데이터 처리)
*   **`extract_composite_key(log)`**: 로그 메시지를 파싱하여 고정 영역 표시를 위한 고유 키(예: `TICKER_MKT`, `TICKER_ODR`)를 추출합니다.
*   **`colorize_log(log)`**: `stock_configuration.json`(사용자 정의 색상) 또는 로그 타입(주문은 초록색, 에러는 빨간색)에 따라 ANSI 색상을 적용합니다.

### Connection Management (연결 관리)
*   시작 시 메인 프로세스에 대한 연결을 자동으로 재시도합니다.
*   파이프 종료(메인 프로그램 업데이트/종료)를 감지하고 정상적으로 종료합니다.

## Dependencies (의존성)
*   `kis.event_pipe`: 클라이언트 측 파이프 연결 함수(`connect_pipe_client`, `receive_log`)를 사용합니다.
*   `stock_configuration.json`: 색상 설정을 위해 사용됩니다.
*   `win32event`, `win32api`, `pywintypes`: Windows Mutex 사용을 위한 라이브러리.
