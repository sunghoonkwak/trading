# Portfolio Retrieval (`src/kis/get_portfolio.py`)

KIS API 및 Google Sheets 데이터를 통합하여 전체 포트폴리오 현황을 조회하는 모듈입니다.

# Core Logic (핵심 로직)

1. **KIS 잔고 조회**: 국내 및 해외 계좌의 실시간 잔고(보유 종목, 평단가, 수익률 등)를 KIS API를 통해 가져옵니다.
2. **GSheet 데이터 병합**: KIS API로 조회되지 않는 자산(패시브 계좌 등) 정보를 Google Sheets에서 읽어와 병합합니다.
3. **환율 적용**: 최신 환율을 적용하여 모든 자산 가치를 USD 및 KRW로 환산합니다.
4. **결과 정규화**: 시스템에서 공통으로 사용할 수 있는 표준 포트폴리오 데이터 구조를 생성합니다.

# Key Functions (주요 함수)

## `get_portfolio`
전체 포트폴리오 데이터를 조회하고 가공하여 반환합니다.

- **출력 (Output)**: `dict` (계좌 정보, 보유 종목, 현금, 메타데이터 포함)

# Configuration (None)
내부적으로 `kis_auth` 및 `gsheet` 설정을 사용합니다.

# Usage Example (사용 예시)

```python
from kis.get_portfolio import get_portfolio

portfolio_data = get_portfolio()
```
