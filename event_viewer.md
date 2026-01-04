# Event Viewer (`event_viewer.py`)

이 모듈은 메인 프로그램으로부터 Named Pipe를 통해 수신한 실시간 시세 데이터와 주문 정보를 표시하는 독립 실행형 터미널 애플리케이션입니다.

## Overview (개요)

**Textual TUI 프레임워크**를 활용하여 3개의 패널로 구성된 인터페이스를 제공합니다:

1. **Orders Panel (상단)**: 활성 주문 목록을 실시간으로 표시합니다.
2. **Quotes Panel (중간)**: 종목별 최신 시세 정보를 표시합니다.
3. **Log Panel (하단)**: 모든 MKT 이벤트의 스크롤 가능한 로그를 표시합니다.

## Key Features (주요 기능)

### 3-Panel Layout (3분할 레이아웃)
*   **OrdersPanel**: `reactive` 속성을 사용하여 주문 추가/삭제 시 자동으로 패널 크기를 조정합니다.
*   **QuotesPanel**: 종목별로 최신 시세만 유지하며 (최대 10개), 중복 없이 업데이트됩니다.
*   **RichLog**: Textual의 내장 위젯으로, MKT 메시지를 시간순으로 기록합니다.

### Message Protocol (메시지 프로토콜)
Named Pipe를 통해 수신되는 메시지는 타입별로 라우팅됩니다:
*   **`MKT|{content}`**: 시세 데이터 → Quotes 패널 + Log 패널
*   **`ODR|{content}`**: 주문 정보 → Orders 패널만
*   **`CLR|ORDERS`**: 주문 목록 초기화

### Process Detection (프로세스 감지)
*   **Windows Named Mutex**: `StevenOpenAPITradingViewer`라는 이름의 뮤텍스(Mutex)를 사용하여 뷰어의 실행 여부를 시스템 전역에서 확실하게 감지합니다.
*   **`acquire_mutex()`**: 뷰어 시작 시 뮤텍스를 생성하여 실행 중임을 알립니다.
*   **`is_running()`**: 메인 프로그램은 이 뮤텍스의 존재 여부를 통해 뷰어 프로세스가 실제로 살아있는지 확인합니다.

### Auto Spawn & Exit (자동 실행 및 종료)
*   **`spawn_viewer()`**: `main.py` 시작 시 Windows Terminal에서 Event Viewer를 자동으로 실행합니다.
*   **Auto Exit**: 메인 프로그램 종료 시 파이프가 닫히면 Event Viewer도 자동으로 종료됩니다.

## Message Format (메시지 포맷)

### Orders (ODR)
```
ODR|{ticker}|{name}|{side}|{qty}|{price}|{state}|{order_id}
```
예: `ODR|AAPL|Apple Inc|Buy|10|$150.00|PLACED|TEST001`

### Market Data (MKT)
```
MKT|{time}|{name}|{ticker}|Bid:{bid}|Last:{price}({vol})|Diff:{diff}({rate}%)|Ask:{ask}
```
예: `MKT|19:26:07|Apple Inc|AAPL|Bid:150.00|Last:151.25(1,200)|Diff:+1.25(0.83%)|Ask:151.50`

### Clear Orders (CLR)
```
CLR|ORDERS
```

## Dependencies (의존성)
*   **`textual`**: Textual TUI 프레임워크 (pip install textual)
*   `kis.event_pipe`: 클라이언트 측 파이프 연결 함수(`connect_pipe_client`, `receive_log`)
*   `win32event`, `win32api`, `pywintypes`: Windows Mutex 사용을 위한 라이브러리
