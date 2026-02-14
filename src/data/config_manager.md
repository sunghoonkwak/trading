# Config Manager (`src/data/config_manager.py`)

JSON 형식의 설정 파일 및 실행 이력 파일을 로드하고 저장하는 기능을 전담하는 모듈입니다.

# Core Logic (핵심 로직)

1. **파일 관리**: `ConfigFile` 열거형(Enum)을 통해 관리 대상 파일들을 중앙에서 정의합니다.
2. **경로 관리**: `~/KIS_config` 디렉토리를 기본 루트로 하여 각 파일의 절대 경로를 생성합니다.
3. **읽기/쓰기**: JSON 데이터를 파싱하여 Python 객체로 변환하거나, 그 반대의 작업을 수행합니다. 쓰기 방지(Read-only) 설정이 된 파일에 대한 보호 로직을 포함합니다.

# Key Functions (주요 함수)

## `load_json`
설정 파일을 읽어와 딕셔너리 또는 리스트로 반환합니다.

- **입력 (Input)**:
  - `file_type` (ConfigFile): 파일 종류.
  - `default` (Any): 파일이 없을 경우 반환할 기본값.
- **출력 (Output)**: `Union[Dict, list]`

## `save_json`
데이터를 지정된 설정 파일에 저장합니다.

- **입력 (Input)**:
  - `file_type` (ConfigFile): 파일 종류.
  - `data` (Any): 저장할 데이터.
- **출력 (Output)**: `bool` (성공 여부)

# Configuration (None)
이 모듈은 설정을 관리하는 모듈 자체이므로 별도의 설정이 필요하지 않습니다.

# Usage Example (사용 예시)

```python
from data.config_manager import ConfigFile, load_json, save_json

# 설정 로드
config = load_json(ConfigFile.STRATEGY_CONFIG)

# 데이터 저장
save_json(ConfigFile.MEMO, {"message": "hello"})
```
