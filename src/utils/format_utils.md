# Formatting Utilities (`src/utils/format_utils.py`)

텍스트 출력 및 숫자 표시 형식을 가공하는 범용 유틸리티 모듈입니다.

## Core Logic (핵심 로직)

1. **문자열 폭 계산**: 한글과 같은 CJK 문자가 포함된 문자열이 터미널에서 올바른 폭을 차지하도록 패딩을 계산합니다.
2. **숫자 포매팅**: 숫자를 읽기 쉽게 천단위 구분자(쉼표)를 추가하거나 소수점 자릿수를 조절합니다.

## Key Functions (주요 함수)

### `get_fixed_width`
CJK 문자를 고려하여 고정된 폭의 문자열을 반환합니다.

### `format_number`
숫자 또는 문자열 숫자를 통화 형식(천단위 콤마)으로 변환합니다.

## Configuration (None)

## Usage Example (사용 예시)

```python
from utils.format_utils import get_fixed_width, format_number

# 정렬된 출력
print(f"| {get_fixed_width('삼성전자', 10)} |")
print(f"가격: {format_number(1234567)}")
```
