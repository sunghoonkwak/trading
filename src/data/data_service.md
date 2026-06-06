# Data Service (`src/data/data_service.py`)

애플리케이션 전반에서 사용되는 데이터를 관리하는 중앙 서비스 모듈입니다.

## Core Logic (핵심 로직)

1. **캐시 관리**: 메모리 캐시를 통해 API 부하를 줄이며, `force_refresh=True` 시 캐시를 무시하고 최신 데이터를 조회합니다. (단, `scope="all"` 조회 시에만 캐시 갱신)
2. **KIS 전용 최적화**: `scope="kis"`일 때 GSheet fetch를 건너뛰는 `kis_only` 플래그를 전달하여 전략 실행 시 불필요한 지연을 방지합니다.
3. **지능형 스코프 필터링**:
   - `all`, `kis`, `passive` 모드를 지원합니다.
   - 현금 자산의 소속 계좌 ID와 이름을 모두 검사하여 데이터가 누락되지 않도록 필터링 로직이 강화되었습니다.
4. **환율 검증**: KRW 보유액을 USD로 환산할 때 양수 기준환율이 필요합니다. 환율이 0 이하이면 포트폴리오 병합 중 예외가 발생해 잘못된 합계를 만들지 않습니다.
5. **스코프 로깅**: 계좌 스코프 필터링 시 대상 계좌 ID와 필터링된 현금 건수를 기록하여 데이터 누락 여부를 확인할 수 있게 합니다.

## Key Functions (주요 함수)

### `get_portfolio_data`
최신 포트폴리오 데이터를 가져오며, `scope` 파라미터에 따라 계좌별로 데이터를 정교하게 분류합니다.

- `force_refresh` (bool): 캐시 무시하고 KIS에서 최신 데이터 조회
- `scope` (str): `"kis"`일 때 GSheet을 건너뛰어 속도 최적화

### `_apply_scope_filter`
ID 또는 계좌명을 기반으로 주식과 현금을 목적에 맞게 걸러내는 핵심 필터링 함수입니다.

## Usage Example (사용 예시)

```python
from data.data_service import get_portfolio_data
# KIS 전용 모드로 리밸런싱용 데이터 조회
kis_data = get_portfolio_data(scope="kis")
```
