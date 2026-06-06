# I/O Utilities (`src/utils/io_utils.py`)

Linux 터미널에서 엔터키 입력 없이 즉시 키 입력을 읽는 모듈입니다.

## Core Logic (핵심 로직)

1. **저수준 입력**: `tty`와 `termios`로 터미널을 raw mode로 전환합니다.
2. **상태 복구**: 입력을 읽은 뒤 기존 터미널 속성을 복구합니다.

## Key Functions (주요 함수)

### `getch`
키보드 입력을 1바이트로 즉시 읽어옵니다.

### `getch_str`
키보드 입력을 문자열로 즉시 읽어옵니다.

## Configuration (None)

## Usage Example (사용 예시)

```python
from utils.io_utils import getch_str

print("아무 키나 누르세요...")
key = getch_str()
print(f"눌린 키: {key}")
```
