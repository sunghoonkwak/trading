# Lock Manager (`src/core/lock_manager.py`)

애플리케이션의 단일 인스턴스 실행을 보장하기 위한 파일 기반 잠금(File-based Locking) 기능을 제공합니다.

# Core Logic (핵심 로직)

`fcntl` 라이브러리를 사용하여 운영체제 레벨의 배타적 락(Exclusive Lock)을 관리합니다.
1. 지정된 경로에 `.app.lock` 파일을 생성하거나 엽니다.
2. `flock(LOCK_EX | LOCK_NB)`를 호출하여 비차단 모드로 락 획득을 시도합니다.
3. 락 획득 성공 시 `True`를 반환하고, 프로세스 종료 시까지 파일 핸들을 유지합니다.
4. 이미 락이 걸려있는 경우 `BlockingIOError`를 감지하여 `False`를 반환합니다.

# Key Functions (주요 함수)

## `acquire_lock`
단일 인스턴스 실행을 위해 잠금 파일에 대한 배타적 락을 획득합니다.

- **입력 (Input)**:
  - `base_dir` (str): 락 파일(`.app.lock`)이 생성될 디렉토리 경로
- **출력 (Output)**: `bool` (락 획득 성공 여부)

# Usage Example (사용 예시)

```python
from core import lock_manager

# 메인 진입점에서 호출
if not lock_manager.acquire_lock(base_dir):
    print("Another instance is running.")
    sys.exit(1)
```
