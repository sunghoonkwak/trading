# Price Utilities (`src/utils/price_utils.py`)

가격 소스 우선순위를 해석하는 범용 유틸리티 모듈입니다.

# Core Logic (핵심 로직)

1. **Current Price Resolution (현재가 해석)**:
   - 호출자가 명시적으로 전달한 `current_prices[ticker]`를 우선 사용합니다.
   - 명시 현재가가 없거나 0 이하이면 보유 잔고의 `holding["cur_price"]`로 fallback합니다.
   - 두 값 모두 유효하지 않으면 `0.0`을 반환하고, 호출자가 전략별 skip/error 처리를 합니다.

# Key Functions (주요 함수)

## `resolve_current_price`
전략 계산, 실행 서비스, 가격 맵 생성 등에서 같은 현재가 우선순위를 적용합니다.

- **입력 (Input)**:
  - `ticker` (str): 가격을 확인할 종목 코드
  - `holding` (Dict): 해당 종목의 보유 잔고 데이터
  - `current_prices` (Dict[str, float]): 외부에서 조회하거나 계산한 현재가 맵
- **출력 (Output)**: `float`
  - `current_prices` 우선, `holding["cur_price"]` fallback 기준의 현재가

# Usage Example (사용 예시)

```python
from utils.price_utils import resolve_current_price

price = resolve_current_price(
    "SOXL",
    holding={"cur_price": 240.0},
    current_prices={"SOXL": 241.2},
)
```
