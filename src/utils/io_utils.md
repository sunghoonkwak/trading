# I/O Utilities (`src/utils/io_utils.py`)

플랫폼(Windows/Linux)에 독립적인 키보드 입력을 처리하는 모듈입니다.

# Core Logic (핵심 로직)

1. **플랫폼 감지**: `sys.platform`을 통해 실행 환경이 Windows인지 POSIX(Linux/Mac)인지 확인합니다.
2. **저수준 입력**: 엔터키 입력 없이 즉시 키 입력을 가로채기 위해 Windows는 `msvcrt`, Linux는 `termios`를 사용합니다.

# Key Functions (주요 함수)

## `getch`
키보드 입력을 1바이트로 즉시 읽어옵니다.

## `getch_str`
키보드 입력을 문자열로 즉시 읽어옵니다.

# Configuration (None)

# Usage Example (사용 예시)

```python
from utils.io_utils import getch_str

print("아무 키나 누르세요...")
key = getch_str()
print(f"눌린 키: {key}")
```
