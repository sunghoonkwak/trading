# Market Utilities (`src/utils/market_utils.py`)

시장 지표 조회 및 주식 시장 캘린더 정보를 제공하는 유틸리티 모듈입니다.
`pandas_market_calendars`와 시간대 라이브러리를 활용하여 정확한 장 운영 정보를 제공합니다.

## Core Logic (핵심 로직)

1. **US Market Status (미국 장 운영 확인)**:
   - 현재 시간이 05:00 ~ 16:00 (ET) 사이인지 확인합니다.
   - 주말(토/일)과 공휴일 여부를 체크합니다.

2. **Market Holiday (휴장일 체크)**:
   - `pandas_market_calendars`를 사용하여 NYSE 등의 휴장 여부를 판별합니다.

3. **Indicator Caching (지표 캐싱)**:
   - Fear & Greed 지수 등 API 호출이 필요한 데이터를 10분 단위로 메모리에 캐싱하여 부하를 줄입니다.

## Key Functions (주요 함수)

### `get_us_market_status`
현재 시점에서 미국 주식 시장의 주문 가능 여부를 확인합니다.

- **출력 (Output)**: `Tuple[bool, str]`
  - `is_allowed`: 주문 가능 여부 (True/False)
  - `message`: 상태 메시지 (예: "Trading Allowed", "Market closed (Holiday)")

### `is_market_holiday`
지정된 날짜와 거래소의 휴장 여부를 확인합니다.

- **입력 (Input)**:
  - `name` (str): 거래소 이름 (기본값: "NYSE")
  - `date` (datetime): 확인할 날짜
- **출력 (Output)**: `bool` (휴장일 여부)

### `get_fear_and_greed`
현재 시장의 Fear & Greed 지수를 조회합니다.

- **출력 (Output)**: `float` (0 ~ 100)

## Configuration (None)
별도의 설정 파일이 없습니다.

## Usage Example (사용 예시)

```python
from utils.market_utils import get_us_market_status

is_allowed, msg = get_us_market_status()
if is_allowed:
    print("Market is open!")
else:
    print(f"Closed: {msg}")
```
