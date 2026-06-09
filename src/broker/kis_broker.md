# KIS Broker Facade (`src/broker/kis_broker.py`)

이 모듈은 앱 소유 영역에서 공식 KIS API wrapper를 감싸는 얇은
facade입니다. `src/kis/kis_api/**`는 공식 배포판 경계로 유지하고,
전략 실행 정책과 테스트 seam은 이 모듈에서 제공합니다.

## Responsibilities

- 해외주식 매수가능금액조회(`inquire_psamount`) 결과에서
  `ovrs_ord_psbl_amt`를 읽어 주문 가능 USD를 반환합니다.
- `StrategyOrder`를 KIS 해외주식 주문 wrapper의 인자로 변환합니다.
- API timeout을 `[API Timeout]` 메시지로 정규화합니다.

## Import Boundary

공식 KIS auth와 endpoint wrapper는 함수 호출 시점에 lazy-load합니다.
따라서 앱 모듈 import만으로 `KIS_config`, credential, token 파일에
접근하지 않아야 합니다.
