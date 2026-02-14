# Storage Module (`storage.py`)

이 모듈은 전략 설정(`strategy_config.json`) 로드와 매매 히스토리 파일(`*_history.json`)의 입출력을 전담하는 중앙 저장소 관리 모듈입니다.

## Purpose (목적)

- **설정 중앙화**: 여러 전략의 설정을 하나의 파일/인터페이스로 관리하여 일관성 유지.
- **I/O 추상화**: 각 전략 모듈에서 파일 경로 및 JSON 처리 로직을 분리하여 코드 중복 제거 및 유지보수성 향상.

## Functions (기능)

### `get_strategy_config(strategy_name: str) -> Dict[str, Any]`

특정 전략의 설정을 로드합니다.

- **Args**:
  - `strategy_name`: 설정 파일 내의 최상위 키 이름 (예: `"raoeo"`, `"value_averaging"`)
- **Returns**: 해당 전략의 설정 딕셔너리. 없으면 빈 딕셔너리(`{}`) 반환.

### `load_history(strategy_name: str) -> Union[List, Dict]`

특정 전략의 히스토리 데이터를 로드합니다.

- **Args**:
  - `strategy_name`: 전략 이름. 파일명은 `{strategy_name}_history.json`으로 자동 매핑됩니다.
- **Returns**: 히스토리 데이터 리스트 또는 딕셔너리. 파일이 없거나 에러 발생 시 빈 리스트(`[]`) 반환.

### `save_history(strategy_name: str, data: Union[List, Dict]) -> bool`

특정 전략의 히스토리 데이터를 저장합니다.

- **Args**:
  - `strategy_name`: 전략 이름.
  - `data`: 저장할 데이터 (List 또는 Dict).
- **Returns**: 저장 성공 시 `True`, 실패 시 `False`.

## Files (관련 파일)

- **설정 파일**: `~/KIS_config/strategy_config.json`
- **히스토리 파일**: `~/KIS_config/{strategy_name}_history.json`
