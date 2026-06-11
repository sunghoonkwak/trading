# KIS Portfolio Source Adapter (`src/kis/portfolio_manager.py`)

KIS API에서 한투 계좌 자산을 조회하고 표준 source 포맷으로 변환하는
KIS 전용 어댑터입니다. 공식 class명은 `KisPortfolioSourceAdapter`이며,
통합 포트폴리오 정책을 소유하지 않습니다.

애플리케이션 코드의 KIS 포트폴리오 진입점은
`broker.kis_portfolio.fetch_kis_portfolio()`입니다. 전체 자산 통합,
GSheet 병합, Toss fallback 정책은 `data.portfolio_integration`이
담당합니다.

## Core Logic (핵심 로직)

1. **KIS REST 조회**: 국내/해외 잔고, 기준환율, 해외 주문가능 USD를
   한투 API에서 읽습니다.
2. **데이터 정규화**: KIS 실계좌 조회 결과를 표준 포트폴리오 source
   포맷으로 변환합니다. 해외 잔고 조회의 기준환율은 `output1.bass_exrt`를
   우선 사용하고, 통화 잔고의 `output2.frst_bltn_exrt`를 보조로
   사용합니다. KIS USD 현금은 `QQQM` 1주 기준 `inquire_psamount`의
   `ovrs_ord_psbl_amt`를 우선 사용합니다.
3. **KIS 계좌 소유자**: 한투 계좌는 곽성훈 계좌로 취급하며
   `owner_01`에 매핑합니다.
4. **오류 추적**: `SESSION FULL` 등 KIS 응답 오류는 빈 잔고로 취급하지
   않고 상위 재시도 경로로 전달합니다.

## Key Functions (주요 함수)

### `_fetch_kis_account_data`
KIS API를 호출하여 실계좌 기준의 국내/해외 보유 종목과 예수금 정보를 가져옵니다.
KRW 자산을 USD로 환산할 수 있도록 해외 잔고 응답에서 양수 기준환율을 추출합니다.
해외 주문가능 USD는 `QQQM`/`NASD`/단가 `1`로 매수가능금액을 조회한
`ovrs_ord_psbl_amt`를 사용하며, 값이 없을 때만 해외 잔고의 기존 현금
필드로 되돌아갑니다.
KIS 숫자 필드는 쉼표가 포함되어도 파싱하고, 개별 보유 종목 파싱 실패는
해당 행만 건너뜁니다.

### `_convert_kis_to_standard`

KIS raw 응답을 `holdings`, `cash_holdings`, `asset_info`, `accounts`를
가진 표준 source 포맷으로 변환합니다.

## Preferred Usage (권장 사용)

```python
from broker.kis_portfolio import fetch_kis_portfolio
kis_source, kis_metadata = fetch_kis_portfolio()
```

## Low-Level Adapter Usage (저수준 어댑터 사용)

```python
from kis.portfolio_manager import KisPortfolioSourceAdapter
kis_raw = KisPortfolioSourceAdapter._fetch_kis_account_data()
kis_source = KisPortfolioSourceAdapter._convert_kis_to_standard(kis_raw)
```
