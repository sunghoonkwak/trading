# Portfolio Manager (`src/kis/portfolio_manager.py`)

KIS API와 Google Sheets로부터 데이터를 수집하여 통합 포트폴리오 정보를 생성하는 모듈입니다.

# Core Logic (핵심 로직)

1. **멀티 소스 수집**: KIS REST API(국내/해외 잔고)와 Google Sheets(외부 자산)로부터 데이터를 병합합니다.
2. **데이터 정규화**: 각기 다른 API 응답 형식을 시스템 표준 포맷(`holdings`, `cash_holdings`, `asset_info`)으로 변환합니다.
3. **계좌 ID 할당**: 수집된 모든 계좌에 고유한 내부 ID(`acc_01` 등)를 부여하고 소유자 정보를 매핑합니다.
4. **오류 추적**: 수집 과정에서 발생한 개별 소스의 오류(GSheet 연결 실패 등)를 메타데이터에 기록하여 부분적인 데이터 활용이 가능하게 합니다.

# Key Functions (주요 함수)

## `get_integrated_portfolio`
전체 수집 및 병합 프로세스를 실행하는 메인 엔트리 포인트입니다.

- **출력 (Output)**: `Dict` (통합 포트폴리오 데이터)

## `_fetch_kis_account_data`
KIS API를 호출하여 국내외 주식 잔고와 예수금 정보를 가져옵니다.

## `_merge_all`
수집된 KIS 데이터와 GSheet 데이터를 최종 표준 포맷으로 병합합니다.

# Configuration (None)

# Usage Example (사용 예시)

```python
from kis.portfolio_manager import PortfolioManager

# 통합 포트폴리오 데이터 생성
portfolio = PortfolioManager.get_integrated_portfolio()
```
