# KIS Wrapper (`src/kis/wrapper.py`)

KIS API의 복잡한 기능을 단순화하여 제공하는 인터페이스 모듈입니다.
내부적으로 `OrderManager`와 `PriceFetcher` 등을 사용하여 비즈니스 로직과 API 명세를 분리합니다.

# Core Logic (핵심 로직)

1. **인터페이스 캡슐화**: 메인 스레드나 전략 모듈에서 자주 사용하는 API 기능(주가 조회, 주문 조회, 동기화)을 쉬운 함수 형태로 제공합니다.
2. **UI 동기화**: 조회된 주문 정보를 터미널 및 웹 뷰어의 상태에 반영(`update_order_state`)합니다.
3. **주가 조회 (REST)**: WebSocket이 아닌 일반 HTTP 요청을 통한 주가 조회를 처리합니다.

# Key Functions (주요 함수)

## `fetch_price`
특정 종목의 최신 주가를 조회합니다.

- **입력 (Input)**: `ticker` (str), `exchange` (str, optional)
- **출력 (Output)**: `float`

## `get_current_price`
`state.market_state`의 캐시된 데이터를 통해 실시간(WebSocket) 현재가를 즉시 반환합니다.
- **입력 (Input)**: `ticker` (str)
- **출력 (Output)**: `float` (가격, 없으면 0.0)

## `sync_open_orders`
현재 미체결 주문 목록을 가져와 UI 표시 상태를 최신화합니다.
- **데이터 정제 (Sanitization)**:
    - 매수/매도 구분을 영문("Buy"/"Sell")으로 변환합니다.
    - 가격 정보에서 통화 기호($)를 제거하고 순수 숫자 문자열로 포맷팅하여 웹 UI 호환성을 보장합니다.
- **주문 시간 전달**:
    - API 응답에서 `ord_tmd` (주문 시간, HHMMSS 형식)를 추출하여 HH:MM:SS 형식으로 변환합니다.
    - `update_order_state`의 `time_str` 파라미터로 전달하여 웹 UI에 실제 주문 시간이 표시되도록 합니다.

## `execute_manage_action`
주문 취소 또는 정정 작업을 실행합니다.

# Configuration (None)

# Usage Example (사용 예시)

```python
from kis import wrapper

# 주가 조회
price = wrapper.fetch_price("SOXL")

# 주문 상태 동기화
wrapper.sync_open_orders()
```
