# 🛠️ Utilities (Utils)

`trading/utils.py` 모듈은 프로젝트 전반에서 공통적으로 사용되는 유틸리티 함수들을 제공합니다. 중복 로직을 제거하고 일관된 포맷팅을 유지하기 위해 사용됩니다.

## 📄 주요 함수

### `get_fear_and_greed() -> float`
Fear & Greed 지수를 가져옵니다. 10분 캐싱을 적용하여 API 호출을 최소화합니다.

- **Returns**: F&G 지수 (0-100). 에러 시 기본값 50.0 반환.

### `get_fixed_width(text: str, width: int = 8) -> str`
한글과 영문이 혼용된 문자열을 고정된 폭으로 정렬하여 반환합니다.

- **Args**:
    - `text`: 정렬할 원본 문자열
    - `width`: 목표 폭 (기본값: 8)
- **Returns**: 패딩이 포함된 고정 폭 문자열

### `safe_cast(val, to_type, default=None)`
값을 특정 타입으로 안전하게 변환합니다. 예외 발생 시 기본값을 반환합니다.

- **Args**:
    - `val`: 변환할 값
    - `to_type`: 목표 타입 (예: `int`, `float`)
    - `default`: 변환 실패 시 반환할 값
- **Returns**: 변환된 값 또는 기본값

### `is_market_holiday(name="NYSE", date=None) -> bool`
지정된 시장이 휴장일인지 확인합니다.

- **Args**:
    - `name`: 시장 이름 (예: 'NYSE', 'NASDAQ'). 기본값은 'NYSE'.
    - `date`: 확인할 날짜. 기본값은 오늘 날짜.
- **Returns**: 휴장일이면 `True`, 아니면 `False`

### `format_number(val, default="0") -> str`
숫자 값을 천 단위 콤마와 함께 포맷팅합니다.

- **Args**:
    - `val`: 포맷팅할 값 (int, float, str 등)
    - `default`: 실패 시 반환할 기본값 (기본값: "0")
- **Returns**: 포맷팅된 문자열 (예: "53,900" 또는 "57.32")
