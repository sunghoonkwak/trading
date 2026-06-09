# Google Sheets Compatibility Wrapper (`src/kis/gsheet.py`)

`src/kis/gsheet.py`는 Google Sheets 포트폴리오 데이터 소스의 호환 래퍼입니다.
새 코드는 `data.gsheet`를 직접 import해야 합니다.

## Current Behavior

- `connect_google_sheet`
- `parse_worksheet_data`

위 public 함수는 `data.gsheet`에서 다시 내보냅니다. 기존 `kis.gsheet` import를
바로 깨지 않기 위한 임시 호환 계층이며, 실제 구현과 운영 문서는
`src/data/gsheet.py`와 `src/data/gsheet.md`를 기준으로 합니다.
