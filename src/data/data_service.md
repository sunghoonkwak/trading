# Data Service (`src/data/data_service.py`)

애플리케이션 전반에서 사용되는 데이터를 관리하는 중앙 서비스 모듈입니다.

# Core Logic (핵심 로직)

1. **캐시 관리**: 메모리 캐시를 통해 API 부하를 줄이며, 로그를 통해 캐시 히트/미스 상태를 추적합니다.
2. **지능형 스코프 필터링**: 
   - `all`, `kis`, `passive` 모드를 지원합니다.
   - 현금 자산의 소속 계좌 ID와 이름을 모두 검사하여 데이터가 누락되지 않도록 필터링 로직이 강화되었습니다.
3. **디버그 로깅**: 데이터 필터링 전후의 자산 수량 및 금액을 상세히 기록하여 데이터 증발 문제를 사전에 방지합니다.

# Key Functions (주요 함수)

## `get_portfolio_data`
최신 포트폴리오 데이터를 가져오며, `scope` 파라미터에 따라 계좌별로 데이터를 정교하게 분류합니다.

## `_apply_scope_filter`
ID 또는 계좌명을 기반으로 주식과 현금을 목적에 맞게 걸러내는 핵심 필터링 함수입니다.

# Usage Example (사용 예시)

```python
from data.data_service import get_portfolio_data
# KIS 전용 모드로 리밸런싱용 데이터 조회
kis_data = get_portfolio_data(scope="kis")
```
