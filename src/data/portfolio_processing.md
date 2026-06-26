# Portfolio Processing (`src/data/portfolio_processing.py`)

이 모듈은 포트폴리오 데이터의 순수 처리 로직을 담당합니다.
KIS thread, Telegram, display alert, 파일 저장 같은 runtime IO에
의존하지 않습니다.

## Responsibilities

- `PortfolioProcessor.merge_holdings`로 계좌별 원천 잔고를 ticker 기준
  보유/현금 pseudo-ticker 구조로 병합합니다.
- `PortfolioProcessor.calculate_stats`로 USD/KRW 주식, 현금, 전체 합계와
  지역/현금 비중을 계산합니다.

## Boundary

`data_service.py`는 포트폴리오 조회 orchestration과 저장/알림을 담당하고,
이 모듈은 계산 가능한 입력 딕셔너리를 받아 deterministic 결과만
반환합니다.
