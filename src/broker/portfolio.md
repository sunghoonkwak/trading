# Broker Portfolio Sources (`src/broker/portfolio.py`)

이 모듈은 data 계층이 사용하는 portfolio source 진입점입니다.

## Responsibilities

- KIS/Toss portfolio source 조회 함수를 한 곳에서 제공합니다.
- data 계층이 개별 증권사 broker 모듈을 직접 알지 않도록 합니다.
- 증권사별 API 호출과 응답 정규화 구현은 각 broker 모듈에 둡니다.

## Source Modules

- `broker.kis_portfolio`: KIS API source 조회와 표준 포맷 변환
- `broker.toss_portfolio`: Toss API source 조회와 표준 포맷 변환
- `broker.strategy_broker`: 전략 실행 계좌 선택 및 주문/매수가능금액 위임
