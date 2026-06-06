# Portfolio Manager (`src/kis/portfolio_manager.py`)

KIS API와 Google Sheets로부터 데이터를 수집하여 통합 포트폴리오 정보를 생성하는 모듈입니다.

## Core Logic (핵심 로직)

1. **멀티 소스 수집**: KIS REST API와 Google Sheets 데이터를 병합합니다. `kis_only=True` 시 GSheet을 건너뛰어 전략 실행 시 속도를 최적화합니다.
2. **데이터 정규화**: KIS 실계좌 조회 결과를 표준 포트폴리오 포맷으로 변환합니다. 해외 잔고 조회의 기준환율은 `output1.bass_exrt`를 우선 사용하고, 통화 잔고의 `output2.frst_bltn_exrt`를 보조로 사용합니다. KIS USD 현금은 `QQQM` 1주 기준 `inquire_psamount`의 `ovrs_ord_psbl_amt`를 우선 사용합니다.
3. **계좌 ID 할당**: 모든 주식 및 현금 자산에 소속 계좌 ID(`account_id`)를 부여하여 후속 필터링(Scope filtering)이 가능하게 합니다.
4. **오류 추적**: `SESSION FULL` 등 KIS 응답 오류는 빈 잔고로 취급하지 않고 상위 재시도 경로로 전달하며, 수집 오류는 메타데이터에 기록합니다.

## Key Functions (주요 함수)

### `get_integrated_portfolio`
전체 프로세스를 실행하는 메인 엔트리 포인트입니다. `kis_only=True` 시 GSheet fetch를 건너뜁니다.

### `_fetch_kis_account_data`
KIS API를 호출하여 실계좌 기준의 국내/해외 보유 종목과 예수금 정보를 가져옵니다.
KRW 자산을 USD로 환산할 수 있도록 해외 잔고 응답에서 양수 기준환율을 추출합니다.
해외 주문가능 USD는 `QQQM`/`NASD`/단가 `1`로 매수가능금액을 조회한
`ovrs_ord_psbl_amt`를 사용하며, 값이 없을 때만 해외 잔고의 기존 현금
필드로 되돌아갑니다.

### `_merge_all`
주식뿐만 아니라 현금 데이터에도 `account_id`를 정확히 매핑하여 병합합니다.

## Usage Example (사용 예시)

```python
from kis.portfolio_manager import PortfolioManager
portfolio = PortfolioManager.get_integrated_portfolio()
```
