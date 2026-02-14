# Market Utilities (`src/utils/market_utils.py`)

시장 지표 조회 및 주식 시장 캘린더 정보를 제공하는 유틸리티 모듈입니다.

# Core Logic (핵심 로직)

1. **지표 캐싱**: Fear & Greed 지수와 같이 빈번한 조회가 불필요한 시장 데이터에 대해 10분 단위의 메모리 캐시를 적용합니다.
2. **휴장일 체크**: `pandas_market_calendars`를 사용하여 특정 거래소(NYSE 등)의 휴장 여부를 판별합니다.

# Key Functions (주요 함수)

## `get_fear_and_greed`
현재 시장의 Fear & Greed 지수를 조회합니다.

- **출력 (Output)**: `float` (0 ~ 100 사이의 값)

## `is_market_holiday`
지정된 날짜와 거래소의 휴장 여부를 확인합니다.

- **입력 (Input)**:
  - `name` (str): 거래소 이름 (기본값: "NYSE")
  - `date` (datetime): 확인할 날짜 (기본값: 현재 시간)
- **출력 (Output)**: `bool` (휴장일인 경우 True)

# Configuration (None)

# Usage Example (사용 예시)

```python
from utils.market_utils import get_fear_and_greed, is_market_holiday

# 시장 상태 확인
fg_index = get_fear_and_greed()
if not is_market_holiday():
    print("Market is open!")
```
