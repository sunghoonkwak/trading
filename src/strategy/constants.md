# Strategy Constants (`src/strategy/constants.py`)

전략 계산에서 공유하는 정책 기본값을 관리하는 모듈입니다.

## Core Logic (핵심 로직)

1. **전략 정책 소유권**: RAOEO, value averaging, rebalancing 기본 임계값은 `strategy` 패키지에서 관리합니다.
2. **설정 fallback 명시**: 사용자 설정에 값이 없을 때 적용되는 기본값을 한곳에서 확인할 수 있습니다.
3. **브로커 독립 주문 의도**: 전략은 `LIMIT`, `LOC` 같은 의미값만 생성하고, KIS/Toss 전용 주문 코드는 브로커 facade에서 변환합니다.
4. **KIS 제약 반영**: RAOEO 매수 가격 상한처럼 전략 로직에 반영되는 운영 안전 마진을 명시합니다.
5. **전략 이력 날짜 규칙**: 전략 실행 이력에서 공유하는 ET 기준 timezone과 날짜 입력 형식 검증 패턴을 관리합니다.

## Key Constants (주요 상수)

- **`DEFAULT_VA_THRESHOLD`**: value averaging 기본 괴리율 임계값.
- **`DEFAULT_REBALANCE_THRESHOLD`**: rebalancing 기본 비중 차이 임계값.
- **`DEFAULT_RAOEO_PROFIT`**: RAOEO 기본 수익률 fallback.
- **`ORDER_TYPE_LIMIT`**: 브로커 독립 지정가 주문 의도.
- **`ORDER_TYPE_LOC`**: 브로커 독립 장마감 지정가 주문 의도.
- **`MAX_BUY_PRICE_RATIO`**: KIS 주문 거절을 피하기 위한 RAOEO 매수가 상한 배율.
- **`TZ_ET`**: 미국 거래일 기준 날짜 계산에 사용하는 Eastern timezone.
- **`STRATEGY_HISTORY_DATE_RE`**: `YYYY-MM-DD` 전략 이력 날짜 형식.
- **`STRATEGY_HISTORY_COMPACT_DATE_RE`**: `YYYYMMDD` 전략 이력 날짜 형식.

## Usage Example (사용 예시)

```python
from strategy.constants import DEFAULT_VA_THRESHOLD, ORDER_TYPE_LIMIT

threshold_rate = config.get("threshold_rate", DEFAULT_VA_THRESHOLD)
order_type = ORDER_TYPE_LIMIT
```
