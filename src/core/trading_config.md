# Trading Config (`src/core/trading_config.py`)

이 모듈은 `stock_configuration.json` 파일로부터 종목별 설정 데이터를 로드하고 관리합니다. `src/core/` 패키지에 위치하여 매매 시스템 전반에서 종목 정보를 조회하는 통합 인터페이스를 제공합니다.

## Purpose (목적)
표시 이름, 시장 유형, UI 색상 선호도와 같은 종목 메타데이터를 중앙에서 관리하여, 코드 수정 없이도 간편하게 설정을 변경할 수 있도록 하는 것입니다.

## Key Functions (주요 함수)

### `strip_market_prefix`
해외 주식 코드에서 시장 접두사(DNAS, DNYS, DAMS)를 제거하여 표시용 티커를 반환합니다.
#### input
- `ticker` (str): 접두사가 포함된 티커 (예: 'DNASNVDA').
#### output
- `str`: 접두사가 제거된 티커 (예: 'NVDA').

### `get_stock_info`
지정된 티커 또는 시장 접두사가 붙은 티커에 대한 설정 데이터를 조회합니다.
- 시장 접두사(예: `DNASNVDA` -> `NVDA`)를 자동으로 처리합니다.
- 설정 파일의 `KR` 및 `US` 리스트를 모두 검색합니다.
#### input
- `ticker` (str): 주식 티커 심볼 (예: 'AAPL', '005930').
#### output
- `dict`: 종목의 설정 객체(이름, 티커, 시장, 색상, 활성여부 등) 또는 찾지 못한 경우 빈 딕셔너리.
    - **Note**: `disabled: true`로 설정된 종목은 로드에서 제외되거나 로깅 시스템에서 무시될 수 있습니다.

### `get_kis_exchange_code`
종목의 시장 정보를 바탕으로 KIS API에서 사용하는 거래소 코드(`NAS`, `NYS`, `AMS`)를 반환합니다.
- **Auto-Mapping**: `NASDAQ` → `NAS`, `NYSE` → `NYS`, `AMEX` → `AMS`
#### input
- `ticker` (str): 종목 티커.
#### output
- `str`: 3글자 KIS 거래소 코드 (기본값: 'NAS').

---

### `get_kis_market_prefix`
해외 주식 실시간 체결 구독 등에 필요한 시장 접두사(`DNAS`, `DNYS`, `DAMS`)가 포함된 전체 코드를 반환합니다.
- 이미 접두사가 포함된 경우 원본을 반환합니다.
#### input
- `ticker` (str): 종목 티커.
#### output
- `str`: 접두사가 포함된 티커 (예: 'DNASQLD').

---

### `update_stock_name`
API에서 수신된 실시간 종목명으로 `stock_configuration.json`의 이름을 동적으로 갱신합니다.
#### input
- `ticker` (str): 종목 코드.
- `new_name` (str): 새로운 종목명.
#### output
- `None` (JSON 파일 업데이트).

## Configuration File (stock_configuration.json)
이 모듈은 `US` 섹션과 `KR` 섹션으로 나뉜 종목 리스트를 관리합니다.
- **QLD**: NYSE Arca 상장 종목이므로 KIS API 조회를 위해 `market`이 `AMEX`로 설정되어야 합니다. (2026-01-01 수정 완료)
