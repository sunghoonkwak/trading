# Logger Management (`src/utils/logger.py`)

시스템 전반의 로깅 설정을 중앙 집중식으로 관리하고, 로그 파일의 순환(Rotation) 및 아카이빙을 처리하는 모듈입니다.

# Core Logic (핵심 로직)

1. **Root Logger 설정**: 시스템 전체에서 사용되는 루트 로거의 핸들러와 포맷을 설정합니다.
2. **로그 순환 (Timed Rotation)**: `TimedRotatingFileHandler`를 사용하여 6시간마다 새로운 로그 파일을 생성하며, 파일명에 타임스탬프를 부여합니다.
3. **로그 아카이빙**: 시스템 시작 시 기존의 최신 로그(`WebSocket_latest.log`)를 `logs/` 폴더로 이동시켜 과거 이력을 보존합니다.
4. **외부 라이브러리 로그 제어**: `httpx`, `telegram`, `apscheduler` 등 외부 라이브러리에서 발생하는 불필요한 로그 레벨을 `INFO`로 고정하여 가독성을 높입니다.

# Key Functions (주요 함수)

## `LogManager.setup`
로깅 시스템을 초기화하고 핸들러를 등록합니다.

- **입력 (Input)**:
  - `base_dir` (str): 기준 디렉토리 경로.
  - `log_name` (str): 생성할 로그 파일 이름 (기본값: `WebSocket_latest.log`).
- **출력 (Output)**: `str` (설정된 로그 파일의 전체 경로)

# Configuration (None)

# Usage Example (사용 예시)

```python
from utils.logger import LogManager

# 메인 시스템 시작 시 호출
LogManager.setup("/app/src")
```
