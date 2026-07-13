# Strategy Broker Service (`src/application/strategy_broker.py`)

`StrategyBrokerService`는 `strategy_config.json`의 `strategy_broker` 값으로
전략 계좌를 선택하는 application orchestration입니다.

- 허용값은 `kis`, `toss`이고 기본값은 `kis`입니다.
- 설정 읽기와 KIS/Toss의 매수 가능 금액·주문 함수는 composition root가
  주입합니다.
- API 필드와 주문 변환은 각 infrastructure broker adapter가 계속 담당합니다.

이 서비스는 configuration 파일이나 concrete broker adapter를 import하지
않습니다.
