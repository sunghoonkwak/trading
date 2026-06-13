# Google Sheets Data Source (`src/data/gsheet.py`)

Google Sheets API를 사용하여 외부 포트폴리오 데이터를 읽어오는 데이터 소스입니다.

## Core Logic (핵심 로직)

1. **인증**: 서비스 계정(Service Account) 키 파일로 Google Cloud API에 인증합니다.
2. **데이터 로드**: 지정된 스프레드시트의 워크시트를 읽습니다.
3. **데이터 가공**: 워크시트 행 데이터를 시스템 표준 포트폴리오 조각으로 파싱합니다.

## Key Functions (주요 함수)

### `connect_google_sheet`
지정한 워크시트 이름(`USD`, `KRW` 등)에 연결하여 worksheet 객체를 반환합니다.

### `parse_worksheet_data`
worksheet 행 데이터를 표준 포트폴리오 조각으로 파싱합니다.

- **출력 (Output)**: `dict` (`holdings`, `accounts`, `asset_info`, `cash_holdings`)
- 계좌는 계좌명 자체로 구분합니다. 예를 들어 `토스`와 `토스 별도`는
  서로 다른 account로 처리됩니다.

## Configuration (`service-account.json`)
Google Cloud 서비스 계정 인증 파일이 필요합니다.

## Usage Example (사용 예시)

```python
from data.gsheet import connect_google_sheet, parse_worksheet_data

worksheet = connect_google_sheet("USD")
data = parse_worksheet_data(worksheet, "USD") if worksheet else {}
```
