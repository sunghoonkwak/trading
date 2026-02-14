# Google Sheets Service (`src/kis/gsheet.py`)

Google Sheets API를 사용하여 외부 자산 데이터를 읽어오는 기능을 제공합니다.

# Core Logic (핵심 로직)

1. **인증**: 서비스 계정(Service Account) 키 파일을 사용하여 Google Cloud API에 인증합니다.
2. **데이터 로드**: 지정된 스프레드시트의 특정 범위를 읽어와 Pandas DataFrame으로 변환합니다.
3. **데이터 가공**: 스프레드시트의 행 데이터를 시스템에서 사용 가능한 딕셔너리 형태로 파싱합니다.

# Key Functions (주요 함수)

## `get_gsheet_data`
구글 시트에서 자산 데이터를 읽어와 반환합니다.

- **출력 (Output)**: `List[Dict]` (보유 종목 정보 리스트)

# Configuration (`service-account.json`)
Google Cloud 서비스 계정 인증 파일이 필요합니다.

# Usage Example (사용 예시)

```python
from kis.gsheet import get_gsheet_data

data = get_gsheet_data()
```
