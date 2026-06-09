# Portfolio Retrieval Compatibility Wrapper (`src/kis/get_portfolio.py`)

통합 포트폴리오 조회를 위한 deprecated 호환 wrapper입니다.
새 코드에서는 `PortfolioManager.get_integrated_portfolio()`를 직접 호출하거나
앱 소유 facade인 `data.data_service.get_portfolio_data()`를 사용합니다.

## Core Logic (핵심 로직)

1. **호환성 유지**: 아직 남아 있을 수 있는 legacy 호출자를 위해 `get_portfolio()` 함수 이름을 유지합니다.
2. **위임 (Delegation)**: 실제 데이터 수집 및 병합 로직은 `PortfolioManager`로 위임합니다.

## Key Functions (주요 함수)

### `get_portfolio`
전체 포트폴리오 데이터를 조회하고 가공하여 반환합니다. 신규 호출자는 이
함수를 직접 사용하지 않는 것을 권장합니다.

- **입력 (Input)**:
  - `kis_only` (bool): `True`면 GSheet을 건너뛰고 KIS 데이터만 조회
- **출력 (Output)**: `dict` (통합 포트폴리오 데이터)

## Configuration (None)

## Usage Example (사용 예시)

```python
from kis.portfolio_manager import PortfolioManager

# 전체 데이터 조회
data = PortfolioManager.get_integrated_portfolio()
```
