# Data Service (`src/data/data_service.py`)

애플리케이션 전반에서 사용되는 데이터를 관리하는 중앙 서비스 모듈입니다.

## Core Logic (핵심 로직)

1. **캐시 관리**: 메모리 캐시를 통해 API 부하를 줄이며, `force_refresh=True` 시 캐시를 무시하고 최신 데이터를 조회합니다. (단, `scope="all"` 조회 시에만 캐시 갱신)
   - 원천별 포트폴리오 통합은 `portfolio_integration.py`, 캐시 타입과
     순수 포트폴리오 변환 로직은 `portfolio_processing.py`에 있고, 이
     모듈은 조회 orchestration, 저장, 알림을 담당합니다.
2. **Broker별 조회 최적화**: `scope="kis"` 또는 `scope="toss"`일 때
   해당 broker API만 조회하여 전략 실행 시 불필요한 GSheet/KIS/Toss
   교차 조회를 방지합니다.
3. **지능형 스코프 필터링**:
   - `all`, `kis`, `toss` 모드를 지원합니다.
   - `all`만 GSheet fallback을 허용합니다. `kis`/`toss`는 주문 판단에
     쓰일 수 있으므로 실시간 broker API 데이터만 사용합니다.
   - 현금 자산의 소속 계좌 ID와 이름을 모두 검사하여 데이터가 누락되지 않도록 필터링 로직이 강화되었습니다.
4. **환율 검증**: KRW 보유액을 USD로 환산할 때 양수 기준환율이 필요합니다. 환율이 0 이하이면 포트폴리오 병합 중 예외가 발생해 잘못된 합계를 만들지 않습니다.
5. **스코프 로깅**: 계좌 스코프 필터링 시 대상 계좌 ID와 필터링된 현금 건수를 기록하여 데이터 누락 여부를 확인할 수 있게 합니다.

## Key Functions (주요 함수)

### `get_portfolio_data`
최신 포트폴리오 데이터를 가져오며, `scope` 파라미터에 따라 계좌별로 데이터를 정교하게 분류합니다.

- `force_refresh` (bool): 캐시를 무시하고 선택한 scope의 최신 데이터 조회
- `scope` (str): `"all"`, `"kis"`, `"toss"` 중 하나. `"all"`은 전체
  포트폴리오 확인용이며 Toss 실패 시 GSheet fallback을 유지합니다.
  `"kis"`/`"toss"`는 전략용 broker 계좌 조회에 사용합니다.

### `_apply_scope_filter`
ID 또는 계좌명을 기반으로 주식과 현금을 목적에 맞게 걸러내는 핵심 필터링 함수입니다.

## Related Modules

- `portfolio_integration.py`: KIS/GSheet source 조회와 raw 포트폴리오 병합
- `portfolio_processing.py`: raw 포트폴리오의 평가액, 통계, merged view 계산

## Usage Example (사용 예시)

```python
from data.data_service import get_portfolio_data
# KIS 전용 모드로 전략용 데이터 조회
kis_data = get_portfolio_data(scope="kis")

# Toss 전용 모드로 전략용 데이터 조회
toss_data = get_portfolio_data(scope="toss")
```
