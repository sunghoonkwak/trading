# KIS Constants (`src/kis/constants.py`)

Korea Investment Securities API 계약에 묶인 시장, 주문, 거래소 코드를 관리하는 모듈입니다.

## Core Logic (핵심 로직)

1. **KIS 코드 소유권**: 주문 구분 코드와 거래소 코드 매핑은 KIS API 호출과 직접 연결되므로 `kis` 패키지에서 관리합니다.
2. **전략 모듈 재사용**: 전략 계산 모듈은 주문 타입 문자열을 직접 쓰지 않고 이 모듈의 상수를 import합니다.
3. **중복 제거**: NAS/NYS/AMS 단축 시장 코드를 KIS 주문 API용 거래소 코드로 변환하는 매핑을 한곳에서 공유합니다.

## Key Constants (주요 상수)

- **`ORDER_TYPE_US_LIMIT`**: 미국 주식 지정가 주문 코드 (`00`).
- **`ORDER_TYPE_US_LOC`**: 미국 주식 장마감 지정가 주문 코드 (`34`).
- **`ORDER_TYPE_KR_MARKET`**: 국내 주식 시장가 주문 코드 (`01`).
- **`EXCHANGE_CODE_MAP`**: 내부 시장 코드에서 KIS 해외 거래소 코드로 변환하는 매핑.

## Usage Example (사용 예시)

```python
from kis.constants import EXCHANGE_CODE_MAP, ORDER_TYPE_US_LIMIT

ovrs_excg_cd = EXCHANGE_CODE_MAP.get(market, market)
order_type = ORDER_TYPE_US_LIMIT
```
