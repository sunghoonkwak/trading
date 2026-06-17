# Portfolio Integration (`src/data/portfolio_integration.py`)

이 모듈은 애플리케이션의 원천별 포트폴리오 데이터를 통합하는 data
계층 소유 모듈입니다.

## Core Logic

1. **Broker 원천 조회 위임**: `broker.portfolio`가 KIS/Toss API 데이터를
   표준 source 포맷으로 변환해 제공합니다.
2. **GSheet 원천 조회**: `data.gsheet`을 통해 수동/외부 자산을 읽습니다.
3. **Toss 원천 대체**: `scope="all"`에서 Toss 조회가 실패하면 GSheet의
   `토스` 데이터를 fallback으로 유지하고 `metadata.toss_error`를
   남깁니다.
4. **통합 raw 포트폴리오 생성**: KIS, GSheet, Toss의 `accounts`,
   `holdings`, `cash_holdings`, `asset_info`를 병합하고 `account_id`를
   부여합니다.
5. **Broker별 최적화**: `scope="kis"`는 KIS만, `scope="toss"`는 Toss만
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

USD/KRW Google Sheets 워크시트를 표준 source 포맷으로 읽습니다.

### `replace_account_source`

GSheet에서 읽은 특정 계정의 holdings/cash/account metadata를 다른 표준
source 데이터로 대체합니다. 현재는 `broker.portfolio`가 Toss API 데이터를
성공적으로 읽었을 때 `토스` 계정에 사용합니다.

### `merge_portfolio_sources`

이미 표준화된 KIS/GSheet source 데이터를 하나의 raw 포트폴리오로
병합합니다. 평가액, 비중, 통계 계산은 `portfolio_processing.py`가
담당합니다.
