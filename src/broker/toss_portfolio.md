# Toss Portfolio Facade (`src/broker/toss_portfolio.py`)

이 모듈은 앱 소유 영역에서 Toss 포트폴리오 조회 경계를 제공합니다.

## Responsibilities

- Toss Open API helpers를 호출해 `토스` 계정 데이터를 읽습니다.
- `/api/v1/holdings` 응답을 표준 source 포맷의 holdings와 asset info로
  변환합니다.
- `/api/v1/buying-power`의 KRW/USD `cashBuyingPower`를 cash holdings로
  변환합니다.

## Import Boundary

`data.portfolio_integration`은 이 facade를 lazy-load한 뒤 표준 source
데이터를 병합합니다. Toss endpoint path, response field, access token,
accountSeq 기본값은 broker 계층에 둡니다.
