# Market Utilities (`src/utils/market_utils.py`)

시장 지표 조회 및 주식 시장 캘린더 정보를 제공하는 유틸리티 모듈입니다.
`pandas_market_calendars`와 시간대 라이브러리를 활용하여 정확한 장 운영 정보를 제공합니다.

## Core Logic (핵심 로직)

1. **US Market Status (미국 장 운영 확인)**:
   - 현재 시간이 05:00 ~ 16:00 (ET) 사이인지 확인합니다.
   - 주말(토/일), 휴장일, 장외 시간은 모두 시장 미개장으로 처리합니다.

2. **Market Closed Day (거래 세션 없음 확인)**:
   - `pandas_market_calendars`를 사용하여 NYSE 거래 세션이 없는 날짜를 판별합니다.
   - 거래 세션 조회는 `get_us_market_status` 내부 구현으로만 사용합니다.

3. **Indicator Caching (지표 캐싱)**:
   - Fear & Greed 지수 등 API 호출이 필요한 데이터를 10분 단위로 메모리에 캐싱하여 부하를 줄입니다.

## Key Functions (주요 함수)

### `get_us_market_status`
현재 시점에서 미국 주식 시장의 주문 가능 여부를 확인합니다. 날짜를
전달하면 해당 날짜의 거래 가능 여부와 현재 ET 시간을 함께 판단합니다.

- **출력 (Output)**: `Dict`
  - `is_market_open`: 주문 가능 여부 (True/False)
  - `message`: 상태 메시지 (예: "Trading Allowed", "Market closed (Holiday)")

### `get_fear_and_greed`
현재 시장의 Fear & Greed 지수를 조회합니다.

- **출력 (Output)**: `float` (0 ~ 100)

## Configuration (None)
별도의 설정 파일이 없습니다.

## Usage Example (사용 예시)

```python
from utils.market_utils import get_us_market_status

status = get_us_market_status()
if status["is_market_open"]:
    print("Market is open!")
else:
    print(f"Closed: {status['message']}")
```
