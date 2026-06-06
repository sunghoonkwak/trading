# Order Manager (`src/kis/order_manager.py`)

국내 및 해외 주식 시장의 미체결 주문을 조회하고, 정정 또는 취소하는 기능을 전담하는 모듈입니다.

## Core Logic (핵심 로직)

1. **주문 조회**: KIS REST API를 사용하여 국내(`inquire_psbl_rvsecncl`) 및 해외(`inquire_nccs`) 시장의 미체결 주문 목록을 가져옵니다.
2. **시장 통합**: 각기 다른 포맷의 국내/해외 주문 데이터를 하나의 Pandas DataFrame으로 통합하고 시장 구분(`_market`) 필드를 추가합니다.
3. **주문 관리**: 사용자가 요청한 주문 번호와 시장 정보를 바탕으로 취소(`02`) 또는 정정(`01`) 명령을 전송합니다.

## Key Functions (주요 함수)

### `fetch_open_orders`
모든 시장의 미체결 주문 목록을 조회합니다.

- **출력 (Output)**: `Tuple[pd.DataFrame, int, int]` (통합 주문 목록, 미국 주문 수, 한국 주문 수)

### `execute_action`
특정 주문에 대해 취소 또는 정정 작업을 수행합니다.

- **입력 (Input)**:
  - `market` (str): 시장 구분 ("KR" 또는 "US")
  - `action_type` (str): 작업 종류 ("1": 정정, "2": 취소)
  - `order_data` (dict): 대상 주문 정보
  - `new_price` (str, optional): 정정할 가격
- **출력 (Output)**: `Tuple[Optional[pd.DataFrame], Optional[str]]` (결과 데이터, 에러 메시지)
- **로깅 (Logging)**: 모든 취소/정정 요청 시 주문 번호와 시장 정보를 기록하며, API 응답 결과(성공/실패 메시지)를 `INFO` 레벨로 남깁니다.

## Configuration (None)

## Usage Example (사용 예시)

```python
from kis.order_manager import OrderManager

# 주문 조회
df, us_count, kr_count = OrderManager.fetch_open_orders()

# 주문 취소
OrderManager.execute_action("US", "2", order_info)
```
