# Google Sheets Service (`src/kis/gsheet.py`)

Google Sheets API를 사용하여 외부 자산 데이터를 읽어오는 기능을 제공합니다.

## Core Logic (핵심 로직)

1. **인증**: 서비스 계정(Service Account) 키 파일을 사용하여 Google Cloud API에 인증합니다.
2. **데이터 로드**: 지정된 스프레드시트의 특정 범위를 읽어와 Pandas DataFrame으로 변환합니다.
3. **데이터 가공**: 스프레드시트의 행 데이터를 시스템에서 사용 가능한 딕셔너리 형태로 파싱합니다.

## Key Functions (주요 함수)

### `connect_google_sheet`
지정한 워크시트 이름(`USD`, `KRW` 등)에 연결하여 worksheet 객체를 반환합니다.

### `parse_worksheet_data`
worksheet 행 데이터를 표준 포트폴리오 조각으로 파싱합니다.

- **출력 (Output)**: `dict` (`holdings`, `accounts`, `asset_info`, `cash_holdings`)

## Configuration (`service-account.json`)
Google Cloud 서비스 계정 인증 파일이 필요합니다.

## Usage Example (사용 예시)

```python
from kis.gsheet import connect_google_sheet, parse_worksheet_data

worksheet = connect_google_sheet("USD")
data = parse_worksheet_data(worksheet, "USD") if worksheet else {}
```
