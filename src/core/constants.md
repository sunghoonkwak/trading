# Core Constants (`src/core/constants.py`)

애플리케이션 공통 런타임 기본값을 관리하는 모듈입니다. 도메인별 계약값은 각 패키지의 constants 모듈이 소유합니다.

## Core Logic (핵심 로직)

1. **앱 공통 기본값**: 설정 루트, 웹 서버 기본값, API 타임아웃, 캐시 주기처럼 여러 패키지가 공유하는 값을 정의합니다.
2. **도메인 경계 유지**: KIS 주문/거래소 코드는 `src/kis/constants.py`, 전략 정책 기본값은 `src/strategy/constants.py`에서 관리합니다.

## Key Constants (주요 상수)

- **`CONFIG_ROOT`**: 사용자 설정 및 데이터 파일이 저장되는 기본 경로 (`~/KIS_config`).
- **`DEFAULT_WEB_PORT`**: 웹 이벤트 뷰어의 기본 포트 (8080).
- **`DEFAULT_USD_KRW_EXCHANGE_RATE`**: 저장된 포트폴리오 이력에 환율이
  없을 때 쓰는 USD/KRW 임시 기준값.
- **`API_TIMEOUT_SHORT` / `API_TIMEOUT_LONG`**: KIS REST 호출 등에 쓰는 기본 타임아웃.
- **`PORTFOLIO_CACHE_EXPIRE`**: 포트폴리오 캐시 만료 시간.
- **`MARKET_STATE_SAVE_INTERVAL`**: 실시간 시세 데이터의 자동 저장 주기 (60초).

## Usage Example (사용 예시)

```python
from core.constants import CONFIG_ROOT

config_path = os.path.join(CONFIG_ROOT, "strategy_config.json")
```
