# KIS REST Client (`src/kis/rest_client.py`)

KIS REST API와의 통신을 전담하며, 네트워크 안정성을 위해 재시도 및 오류 처리 로직이 강화된 모듈입니다.

# Core Logic (핵심 로직)

1. **자동 재시도 (`@retry_on_exception`)**: 네트워크 일시 오류나 API 서버 응답 지연 시 최대 3회까지 자동으로 재시도합니다.
2. **지수 백오프 (Exponential Backoff)**: 재시도 간격을 2초, 4초, 8초와 같이 점진적으로 늘려 서버 부하를 방지합니다.
3. **커스텀 예외 처리**: `KISAPIError` 및 `KISAuthError`를 통해 발생한 오류의 성격을 명확히 구분하여 보고합니다.
4. **상태 업데이트**: 인증 상태 변화를 즉시 시스템 상태(`state.system_state`)에 반영합니다.

# Key Functions (주요 함수)

## `authenticate`
REST API 접근 토큰을 발급받습니다. 실패 시 최대 3회 재시도합니다.

## `authenticate_ws`
WebSocket 접속키를 발급받습니다.

## `get_portfolio`
현재 계좌의 전체 포트폴리오 데이터를 조회합니다. `kis_only=True` 시 GSheet을 건너뛰어 전략 실행 시 응답 속도를 최적화합니다.

# Configuration (None)

# Usage Example (사용 예시)

```python
from kis.rest_client import RESTClient

try:
    # 안전하게 포트폴리오 조회 (자동 재시도 포함)
    result = RESTClient.get_portfolio()
except KISAPIError as e:
    print(f"API 호출 최종 실패: {e}")
```
