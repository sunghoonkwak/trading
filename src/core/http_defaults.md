# HTTP Defaults (`src/core/http_defaults.py`)

## Overview

런타임 프로세스 안의 `requests` 기반 외부 API 호출에 공통 기본값을
설치합니다. 현재는 명시적 timeout이 없는 요청에 `API_TIMEOUT_SHORT`
기본 timeout을 적용합니다.

## Key Functions

### `install_requests_default_timeout(requests_module=None, default_timeout=API_TIMEOUT_SHORT)`

`requests.api.request`와 `requests.Session.request`에 기본 timeout wrapper를
설치합니다.

- 호출자가 `timeout`을 직접 넘기면 그 값을 유지합니다.
- `timeout`이 없을 때만 `default_timeout`을 추가합니다.
- 같은 프로세스에서 여러 번 호출되어도 이미 설치된 wrapper를 다시 감싸지
  않습니다.

이 함수는 `src/main.py` 시작 시 호출되며, KIS, Toss, Telegram 등 런타임
프로세스 안에서 사용하는 `requests` 호출이 무기한 대기하는 것을 막기 위한
의도적인 전역 기본값입니다.
