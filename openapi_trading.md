# 자동 거래 시스템 (KIS OpenAPI Trading System)

## 1. 목적
한국투자증권(KIS) OpenAPI를 활용하여 실시간 시세 조회 및 자동 매매를 수행하는 시스템입니다. 현재는 실시간 국내 주식 호가(H0UNASP0) 및 체결가(H0UNCNT0) 수신, 계좌 잔고 조회, 그리고 보안 인증 체계가 구현되어 있습니다.

## 2. Folder tree
```text
.
├── trading/                     ## core implementation folder
│   ├── kis_api/                ## KIS API specialized package
│   │   ├── domestic_stock/     ## Domestic stock related modules
│   │   │   ├── asking_price_total/ ## Real-time order book (H0UNASP0)
│   │   │   ├── ccnl_total/         ## Real-time conclusion (H0UNCNT0)
│   │   │   └── ...                 ## other specialized modules
│   │   ├── key/                ## encryption & security utilities
│   │   │   ├── key.py          ## Password-based secret loading
│   │   │   ├── generate_credentials.py
│   │   │   └── validate_credentials.py
│   │   └── kis_auth.py         ## REST/WebSocket auth & communication library
│   ├── main.py                 ## entry point script (Interactive Menu & WS)
│   ├── rebalance.py            ## (WIP) Trading logic
│   ├── target_weight.json      ## (WIP) Target portfolio weights
│   └── openapi_trading.md      ## 프로젝트 문서
├── credentials.enc             ## 암호화된 API 키 저장소
└── .gitignore                  ## Git 제외 설정
```

## 3. Tools & Dependencies
1. **Language**: Python 3.12+
2. **Core Libraries**:
   - `requests`: REST API 통신
   - `websockets`: 실시간 시세 수신
   - `pandas`: 데이터 프레임 처리
   - `cryptography`: API 키 암호화 (Fernet)
   - `pycryptodome`: KIS 실시간 데이터 복호화 (AES-CBC)
   - `PyYAML`: 설정 파일 관리

## 4. Implementation Details
1. **Security-First Approach**:
   - `App Key`, `App Secret`, `HTS ID`는 `PBKDF2`와 `Fernet`으로 암호화되어 관리됩니다.
   - 실행 시 비밀번호 입력을 통해 동적으로 복호화하여 사용합니다.
2. **Structured API Package**:
   - `kis_api` 패키지 구조를 도입하여 기능별(국내주식, 해외주식, 인증 등)로 모듈화되었습니다.
   - `domestic_stock` 하위의 개별 모듈(`asking_price_total`, `ccnl_total` 등)을 통해 필요한 데이터만 구독 가능합니다.
3. **Enhanced Logging & UI**:
   - **Multi-level Log Control**: 메뉴에서 **Enter** 입력을 통해 실시간 데이터의 로그 레벨을 순환 변경합니다.
     - `ERROR(0)` -> `INFO(1)` -> `DEBUG(2)` 순으로 순환하며 터미널 출력 범위를 제어합니다.
   - **Colored Logging**: 토큰 만료 알림 및 중요 상태 메시지에 색상 코드를 적용하여 가독성을 높였습니다.
   - **Dynamic Filename**: 실행 시점의 타임스탬프를 포함한 로그 파일(WebSocket_YY_MM_DD_HH_MM_SS.log)을 생성합니다.
4. **Account Management**:
   - REST API를 통해 국내 주식 계좌의 현금 잔고, 주문 가능 금액, 자산 총액 등을 실시간으로 조회할 수 있습니다.
5. **Real-time Data Processing**:
   - `KISWebSocket` 클래스가 비동기 스레드에서 동작하며, `on_result` 콜백을 통해 체결과 호가 데이터를 구분하여 처리합니다.
   - 수신된 데이터는 `pandas.DataFrame`으로 즉시 변환되어 분석에 활용됩니다.
