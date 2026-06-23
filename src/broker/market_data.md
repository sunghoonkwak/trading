# Market Data Facade (`src/broker/market_data.py`)

이 모듈은 앱 소유 영역에서 시장 데이터 조회 경계를 제공합니다.

## Responsibilities

- `fetch_prices(tickers)`를 제공합니다. Toss Invest `/api/v1/prices` 다건
  현재가 조회를 우선 사용하고, 누락된 종목만 KIS 단건 조회로 보완합니다.
- `fetch_price(ticker, exchange=None)`를 제공합니다. 이 함수는 KIS REST 단건
  fallback이며 기존 호출부 호환을 위해 유지합니다.
- `get_current_price(ticker)`를 제공합니다.
  이 함수는 단건 호출부 호환용 래퍼이며 내부적으로 `fetch_prices([ticker])`를
  사용합니다.
- KIS fallback은 공식 KIS price endpoint wrapper를 호출합니다.
  `KIS_ENABLE_REST_API=false`이면 KIS REST 가격 조회는 `0.0`을 반환합니다.
  이 플래그는 Toss 다건 현재가 조회를 막지 않고, KIS fallback만 차단합니다.
- 전략/데이터 서비스가 KIS 영역의 compat wrapper에 직접 의존하지 않도록
  하는 전환 seam입니다.

## Import Boundary

KIS wrapper는 함수 호출 시점에 lazy-load합니다. 따라서 앱 모듈 import만으로
KIS 인증 파일이나 runtime 상태에 접근하지 않아야 합니다.
