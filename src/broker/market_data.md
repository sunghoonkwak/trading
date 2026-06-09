# Market Data Facade (`src/broker/market_data.py`)

이 모듈은 앱 소유 영역에서 시장 데이터 조회 경계를 제공합니다.

## Responsibilities

- `fetch_price(ticker, exchange=None)`를 제공합니다.
- `get_current_price(ticker)`를 제공합니다.
- 현재 구현은 기존 `kis.wrapper.fetch_price`로 lazy 위임합니다.
- 전략/데이터 서비스가 `kis.wrapper`에 직접 의존하지 않도록 하는
  전환 seam입니다.

## Import Boundary

KIS wrapper는 함수 호출 시점에 lazy-load합니다. 따라서 앱 모듈 import만으로
KIS 인증 파일이나 runtime 상태에 접근하지 않아야 합니다.
