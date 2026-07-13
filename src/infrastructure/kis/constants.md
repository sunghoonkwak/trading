# KIS Constants (`src/infrastructure/kis/constants.py`)

KIS API 계약에 묶인 시장, 주문, 거래소 코드를 관리합니다. 주문 구분 코드와
거래소 코드 매핑은 KIS API 호출에 직접 연결되므로 KIS infrastructure package가
소유합니다.

주요 항목은 `ORDER_TYPE_US_LIMIT`, `ORDER_TYPE_US_LOC`,
`ORDER_TYPE_KR_MARKET`, `EXCHANGE_CODE_MAP`입니다. 애플리케이션과 domain
전략은 broker-neutral order type만 사용하고, KIS adapter가 이 코드를 사용합니다.
