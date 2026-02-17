# Portfolio Retrieval Interface (`src/kis/get_portfolio.py`)

통합 포트폴리오 조회를 위한 상위 인터페이스 모듈입니다.
모든 로직은 `PortfolioManager`로 위임하여 구현과 호출을 분리합니다.

# Core Logic (핵심 로직)

1. **위임 (Delegation)**: 실제 데이터 수집 및 병합 로직을 수행하는 `PortfolioManager`를 호출합니다.
2. **호환성 유지**: 기존 시스템 코드들이 참조하는 `get_portfolio()` 함수 이름을 유지하여 리팩토링으로 인한 사이드 이펙트를 최소화합니다.

# Key Functions (주요 함수)

## `get_portfolio`
전체 포트폴리오 데이터를 조회하고 가공하여 반환합니다.

- **입력 (Input)**:
  - `kis_only` (bool): `True`면 GSheet을 건너뛰고 KIS 데이터만 조회
- **출력 (Output)**: `dict` (통합 포트폴리오 데이터)

# Configuration (None)

# Usage Example (사용 예시)

```python
from kis.get_portfolio import get_portfolio

# 전체 데이터 조회
data = get_portfolio()
```
