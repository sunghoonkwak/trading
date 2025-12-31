# trading_config.md

이 모듈은 `stock_configuration.json` 파일로부터 종목별 설정 데이터를 로드하고 관리합니다.

## Purpose (목적)
표시 이름, 시장 유형, UI 색상 선호도와 같은 종목 메타데이터를 중앙에서 관리하여, 코드 수정 없이도 간편하게 설정을 변경할 수 있도록 하는 것입니다.

## Function (기능)

### strip_market_prefix
해외 주식 코드에서 시장 접두사(DNAS, DNYS, DAMS)를 제거하여 표시용 티커를 반환합니다.
#### input
- `ticker` (str): 접두사가 포함된 티커 (예: 'DNASNVDA').
#### output
- `str`: 접두사가 제거된 티커 (예: 'NVDA').

### get_stock_info
지정된 티커 또는 시장 접두사가 붙은 티커에 대한 설정 데이터를 조회합니다.
- 시장 접두사(예: `DNASNVDA` -> `NVDA`)를 자동으로 처리합니다.
- 설정 파일의 `KR` 및 `US` 리스트를 모두 검색합니다.
#### input
- `ticker` (str): 주식 티커 심볼 (예: 'AAPL', '005930').
#### output
- `dict`: 종목의 설정 객체(이름, 티커, 시장, 색상, 활성여부 등) 또는 찾지 못한 경우 빈 딕셔너리.
    - **Note**: `disabled: true`로 설정된 종목은 로드에서 제외되거나 로깅 시스템에서 무시될 수 있습니다.

### update_stock_name
API에서 수신된 실시간 종목명으로 `stock_configuration.json`의 이름을 동적으로 갱신합니다.
#### input
- `ticker` (str): 종목 코드.
- `new_name` (str): 새로운 종목명.
#### output
- `None` (JSON 파일 업데이트).
