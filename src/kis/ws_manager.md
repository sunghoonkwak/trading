# KIS WebSocket Manager (`src/kis/ws_manager.py`)

실시간 시세 수신 및 체결 통보를 위한 WebSocket 연결과 구독(Subscription)을 관리합니다.

## Core Logic (핵심 로직)

1. **인스턴스 관리**: `KISWebSocket` 객체를 생성하고 백그라운드 스레드에서 실행합니다.
2. **구독 자동화**: `trading_config.json`에 설정된 관심 종목들을 국내/해외로 구분하여 자동으로 구독 신청합니다.
3. **체결 통보**: 사용자의 HTS ID를 기반으로 주문 체결 알림을 구독합니다.
4. **콜백 연결**: 수신된 실시간 데이터를 처리할 핸들러(`on_result`)와 연결합니다.

## Key Functions (주요 함수)

### `initialize`
WebSocket 인스턴스를 생성하고, 모든 종목 구독을 마친 뒤 연결 스레드를 시작합니다.

- **출력 (Output)**: `bool` (성공 여부)

### `is_alive`
WebSocket 스레드가 정상적으로 실행 중인지 확인합니다.

## Configuration (`trading_config.json`)
관심 종목(KR/US 섹션) 목록을 참조하여 실시간 시세 구독 대상을 결정합니다.

## Usage Example (사용 예시)

```python
from kis.ws_manager import WSManager

ws = WSManager()
ws.initialize()
```
