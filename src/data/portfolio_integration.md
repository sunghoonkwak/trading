# Portfolio Integration (`src/data/portfolio_integration.py`)

이 모듈은 애플리케이션의 원천별 포트폴리오 데이터를 통합하는 data
계층 소유 모듈입니다.

## Core Logic

1. **Broker 원천 조회 위임**: `broker.portfolio`가 KIS/Toss API 데이터를
   표준 source 포맷으로 변환해 제공합니다.
2. **GSheet 원천 캐시**: `data.gsheet`을 통해 읽은 수동/외부 자산 source를
   메모리에 보관합니다. 최초 사용 또는 startup warmup 때 한 번 읽고,
   이후에는 Telegram `/gsheet` 명령으로 갱신합니다.
3. **Toss 원천 대체**: `scope="all"`에서 Toss 조회가 실패하면 GSheet의
   `토스` 데이터를 fallback으로 유지하고 `metadata.toss_error`를
   남깁니다.
4. **GSheet 가격 보강**: GSheet에서 읽은 현재가는 버리고, Toss 보유조회
   가격이 없는 보유 종목만 Toss `/api/v1/prices` 현재가로 채웁니다.
   가격을 못 받은 종목은 `cur_price=0`으로 두고 Telegram 경고를 보냅니다.
5. **통합 raw 포트폴리오 생성**: KIS, GSheet, Toss의 `accounts`,
   `holdings`, `cash_holdings`, `asset_info`를 병합하고 `account_id`를
   부여합니다.
6. **Broker별 최적화**: `scope="kis"`는 KIS만, `scope="toss"`는 Toss만
   조회합니다. 전략 실행은 `strategy_broker` 설정값을 `kis` 또는 `toss`
   scope로 직접 전달하며, GSheet fallback은 전체 확인용 `scope="all"`에만
   허용됩니다.

## Key Functions

### `get_integrated_portfolio`

`scope`에 따라 broker source와, 필요 시 GSheet 원천을 조회해
`data.data_service`가 처리할 raw 포트폴리오 구조를 반환합니다.

- `all`: KIS, GSheet, Toss를 통합 조회합니다. Toss 실패 시 GSheet의
  `토스` 계정 데이터를 fallback으로 유지합니다.
- `kis`: KIS API 데이터만 조회합니다.
- `toss`: Toss API 데이터와 Toss 환율만 조회합니다. 주문 판단에 쓰일 수
  있으므로 GSheet fallback은 사용하지 않습니다.

### `fetch_gsheet_portfolio`

USD/KRW Google Sheets 워크시트를 표준 source 포맷으로 읽습니다. 시트의
현재가 열은 포트폴리오 평가에 사용하지 않습니다.

### `get_cached_gsheet_portfolio`

메모리에 저장된 GSheet source를 반환합니다. 캐시가 비어 있으면 한 번
`fetch_gsheet_portfolio`를 호출해 초기화합니다. 반환값은 복사본이라
가격 보강 과정에서 캐시 원본이 변경되지 않습니다.

### `refresh_gsheet_cache`

Google Sheets를 다시 읽어 GSheet source 캐시를 교체합니다. Telegram
`/gsheet` 명령과 startup warmup에서 사용하며, 보유 종목/현금/계정 수와
성공 또는 경고 상태를 반환합니다.

### `fetch_toss_prices`

Toss market data `/api/v1/prices`로 현재가를 다건 조회합니다. GSheet
보유분 가격 보강에서는 KIS fallback을 사용하지 않습니다.

### `fill_missing_current_prices_from_toss`

broker 원천 가격이 없는 holding에 Toss 현재가를 채웁니다. Toss 가격이
누락되면 해당 holding의 `cur_price`를 `0.0`으로 설정하고 Telegram 경고를
보냅니다.

### `replace_account_source`

GSheet에서 읽은 특정 계정의 holdings/cash/account metadata를 다른 표준
source 데이터로 대체합니다. 현재는 `broker.portfolio`가 Toss API 데이터를
성공적으로 읽었을 때 `토스` 계정에 사용합니다.

### `merge_portfolio_sources`

이미 표준화된 KIS/GSheet source 데이터를 하나의 raw 포트폴리오로
병합합니다. 평가액, 비중, 통계 계산은 `portfolio_processing.py`가
담당합니다.
