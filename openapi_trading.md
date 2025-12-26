# 자동 거래 시스템 (KIS OpenAPI Trading System)

## 1. 목적
한국투자증권(KIS) OpenAPI를 활용하여 실시간 시세 조회 및 자동 매매를 수행하는 시스템입니다. 현재는 실시간 국내 주식 호가(H0UNASP0) 및 체결가(H0UNCNT0) 수신, 매수 가능 금액 및 예수금 조회, 그리고 보안 인증 체계가 구현되어 있습니다.

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
│   ├── stock_name.json         ## Stock code to name mapping
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
   - `msvcrt`: Windows용 비차단 키 입력 처리

## 4. Implementation Details
1. **Security-First Approach**:
   - `App Key`, `App Secret`, `HTS ID`는 `PBKDF2`와 `Fernet`으로 암호화되어 관리됩니다.
   - 실행 시 비밀번호 입력을 통해 동적으로 복호화하여 사용합니다.
2. **Structured API Package**:
   - `kis_api` 패키지 구조를 도입하여 기능별(국내주식, 해외주식, 인증 등)로 모듈화되었습니다.
3. **Enhanced Logging & UI**:
   - **Multi-level Log Control**: 메뉴에서 **0번** 입력을 통해 실시간 데이터의 로그 레벨을 순환 변경합니다.
   - **Market Data with Names**: `stock_name.json`을 통해 종목 코드를 종목명으로 자동 변환하여 출력합니다.
   - **Non-blocking Return**: `msvcrt.getch()`를 사용하여 조회 결과 확인 후 아무 키나 눌러 메뉴로 즉시 복귀할 수 있습니다.
   - **Raw Data Logging**: API 응답 원본을 타임스탬프가 포함된 로그 파일에 JSON 형식으로 상세히 기록합니다.
4. **Account & Orderable Info**:
   - `inquire-psbl-order` (TTTC8908R) API를 호출하여 한국투자증권 앱과 일치하는 정확한 **주문가능원화(nrcvb_buy_amt)**를 조회합니다.
   - 예수금 총액 및 자산 총액도 함께 표시하여 계좌 상태를 한눈에 파악할 수 있습니다.
5. **Real-time Data Processing**:
   - `KISWebSocket` 클래스가 비동기 스레드에서 동작하며, `on_result` 콜백을 통해 데이터를 실시간으로 처리합니다.
   - 수신된 데이터는 시각, 종목명, 현재가, 대비, 거래량 등을 포함한 정형화된 포맷으로 출력됩니다.
