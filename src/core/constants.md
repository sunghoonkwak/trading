# Global Constants (`src/core/constants.py`)

시스템 전반에서 사용되는 고정된 설정값, 매직 넘버, API 코드 등을 중앙 집중식으로 관리하는 모듈입니다. `src/core/` 패키지에 위치하여 어디서든 일관된 상수를 참조할 수 있게 합니다.

# Core Logic (핵심 로직)

1. **중앙 관리**: 하드코딩된 값들을 한곳으로 모아 코드 유지보수성과 가독성을 높입니다.
2. **범주화**: 경로, 네트워크, 타임아웃, 시장/주문 코드 등으로 상수를 분류하여 정의합니다.
3. **시장별 구분**: KIS API의 특성에 맞춰 국내(KR)와 해외(US)의 주문 유형 코드를 엄격히 분리합니다.

# Key Constants (주요 상수)

- **`CONFIG_ROOT`**: 사용자 설정 및 데이터 파일이 저장되는 기본 경로 (`~/KIS_config`).
- **`DEFAULT_WEB_PORT`**: 웹 이벤트 뷰어의 기본 포트 (8080).
- **`ORDER_TYPE_US_LOC`**: 미국 주식 장마감 지정가 주문 코드 (`34`).
- **`ORDER_TYPE_KR_MARKET`**: 국내 주식 시장가 주문 코드 (`01`).
- **`MARKET_STATE_SAVE_INTERVAL`**: 실시간 시세 데이터의 자동 저장 주기 (60초).

# Usage Example (사용 예시)

```python
from core import constants
# 또는
from core.constants import ORDER_TYPE_US_LOC

# 전략 계산 시 상수 사용
order_type = ORDER_TYPE_US_LOC
```
