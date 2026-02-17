# Portfolio Manager (`src/kis/portfolio_manager.py`)

KIS API와 Google Sheets로부터 데이터를 수집하여 통합 포트폴리오 정보를 생성하는 모듈입니다.

# Core Logic (핵심 로직)

1. **멀티 소스 수집**: KIS REST API와 Google Sheets 데이터를 병합합니다. `kis_only=True` 시 GSheet을 건너뛰어 전략 실행 시 속도를 최적화합니다.
2. **데이터 정규화**: KIS 모의투자 계좌의 특수한 필드(`ovrs_relt_proc_amt`) 등을 자동으로 감지하여 표준 포맷으로 변환합니다.
3. **계좌 ID 할당**: 모든 주식 및 현금 자산에 소속 계좌 ID(`account_id`)를 부여하여 후속 필터링(Scope filtering)이 가능하게 합니다.
4. **오류 추적**: 수집 오류를 메타데이터에 기록합니다.

# Key Functions (주요 함수)

## `get_integrated_portfolio`
전체 프로세스를 실행하는 메인 엔트리 포인트입니다. `kis_only=True` 시 GSheet fetch를 건너뜁니다.

## `_fetch_kis_account_data`
KIS API를 호출하여 예수금 정보를 가져올 때, 실계좌와 모의계좌의 차이를 흡수합니다.

## `_merge_all`
주식뿐만 아니라 현금 데이터에도 `account_id`를 정확히 매핑하여 병합합니다.

# Usage Example (사용 예시)

```python
from kis.portfolio_manager import PortfolioManager
portfolio = PortfolioManager.get_integrated_portfolio()
```
