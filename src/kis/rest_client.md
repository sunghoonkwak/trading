# KIS REST Client (`src/kis/rest_client.py`)

KIS REST API와의 통신을 전담하는 모듈입니다.
인증(Authentication) 및 계좌 잔고 조회(Portfolio) 등의 동기식 HTTP 요청을 처리합니다.

# Core Logic (핵심 로직)

1. **인증 관리**: REST API 및 WebSocket 연결을 위한 토큰 발급을 수행합니다.
2. **데이터 조회**: `kis.get_portfolio` 모듈을 호출하여 계좌의 전체 자산 및 종목 현황을 가져옵니다.
3. **상태 업데이트**: 인증 진행 상황 및 결과(성공/실패)를 `thread_state`에 반영하여 시스템 전체에서 인지할 수 있게 합니다.

# Key Functions (주요 함수)

## `authenticate`
KIS REST API 토큰을 발급받습니다.

- **출력 (Output)**: `Dict` (상태 정보)

## `authenticate_ws`
WebSocket 접속을 위한 보조 인증(접속키 발급)을 수행합니다.

- **출력 (Output)**: `Dict`

## `get_portfolio`
현재 계좌의 전체 포트폴리오 데이터를 조회합니다.

- **출력 (Output)**: `Dict` (원시 포트폴리오 데이터)

# Configuration (None)
별도의 설정 파일이 없으며 `kis_auth` 설정을 사용합니다.

# Usage Example (사용 예시)

```python
from kis.rest_client import RESTClient

# 포트폴리오 조회
result = RESTClient.get_portfolio()
```
