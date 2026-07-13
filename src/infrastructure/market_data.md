# Market Data Adapter (`src/infrastructure/market_data.py`)

KIS와 Toss 가격 API를 함께 사용하는 provider-neutral infrastructure
adapter입니다.

- `fetch_prices(tickers)`는 Toss 다건 현재가를 우선 조회하고, 누락 종목만 KIS
  REST 단건 조회로 보완합니다.
- `fetch_price(ticker, exchange=None)`는 KIS REST 단건 fallback입니다.
- `KIS_ENABLE_REST_API=false`는 KIS fallback만 `0.0`으로 차단하며 Toss
  조회는 계속 허용합니다.

KIS wrapper는 호출 시 lazy-load하므로 adapter import만으로 인증 파일이나
runtime 상태에 접근하지 않습니다.
