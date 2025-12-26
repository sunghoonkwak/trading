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
│   ├── stock_config.json       ## Stock configuration (names, RGB, disabled)
│   ├── target_weight.json      ## (WIP) Target portfolio weights
│   └── openapi_trading.md      ## 프로젝트 문서
├── credentials.enc             ## 암호화된 API 키 저장소 (Root level)
└── .gitignore                  ## Git 제외 설정
```

## 3. Tools & Dependencies
1. **Language**: Python 3.12+
2. **External Libraries (Install via pip)**:
   - `requests`: REST API 통신
   - `websockets`: 실시간 시세 수신
   - `pandas`: 데이터 프레임 처리
   - `cryptography`: API 키 암호화 (Fernet)
   - `pycryptodome`: KIS 실시간 데이터 복호화 (AES-CBC)
   - `PyYAML`: 설정 파일 관리
3. **Standard Libraries (Built-in)**:
   - `msvcrt`: Windows 전용 비차단 키 입력 처리
   - `unicodedata`: 한글/영문 폭 계산 및 정렬 도움
   - `logging`, `threading`, `re`, `json` 등

## 4. Implementation Details
1. **Security-First Approach**:
   - `App Key`, `App Secret`, `HTS ID`는 `PBKDF2`와 `Fernet`으로 암호화되어 관리됩니다.
   - 실행 시 비밀번호 입력을 통해 동적으로 복호화하여 사용합니다.
2. **Flexible Stock Configuration**:
   - `stock_config.json`을 통해 종목별 **이름, 고유 RGB 색상, 구독 활성화 여부(disabled)**를 중앙 관리합니다.
   - 프로젝트 실행 시 `disabled: false`인 종목만 자동으로 구독 목록에 포함됩니다.
3. **Advanced Terminal UI**:
   - **Prioritized Latest Status**: 로그 영역 상단에 구독 중인 모든 종목의 **최신 체결/호가 상태**를 1줄씩 고정하여 실시간 현황판 역할을 수행합니다.
   - **Visual Width Alignment**: 한글(2폭)과 영문(1폭)의 차이를 계산하여 종목명이 달라도 로그 줄이 흐트러지지 않도록 **10자 고정 폭 정렬**을 적용했습니다.
   - **Color-Coded Tracks**: 종목별 고유 RGB 색상을 적용하여 수많은 로그 흐름 속에서도 특정 종목의 데이터를 즉시 구분할 수 있습니다.
   - **Clean Screen Refresh**: 메뉴와 로그 영역 사이의 잔상을 제거하기 위해 ANSI Escape Code(`CLEAR_LINE`)를 활용한 정밀한 화면 갱신을 구현했습니다.
4. **Combined Account Info**:
   - **KRW/USD Unified Inquiry**: 국내 주식 주문 가능 금액(`TTTC8908R`)과 해외 주식 예수금 현황(`CTRP6504R`)을 통합하여 한 번에 조회할 수 있는 기능을 제공합니다.
   - **Data Robustness**: API 응답 형식이 리스트나 딕셔너리로 가변적인 경우에도 안정적으로 데이터를 추출하여 원화 및 외화 잔고를 정확히 표시합니다.
5. **Robust Data Handling**:
   - **Multi-record Processing**: 웹소켓 메시지 하나에 여러 건의 데이터가 묶여 올 경우(`count > 1`), 이를 누락 없이 개별 레코드로 분리하여 처리합니다.
   - **Async Stability**: 구독 요청 간에 짧은 비동기 지연(`asyncio.sleep`)을 주어 서버의 요청 제한(Throttling)을 방지합니다.

## 5. How to use
1. 터미널에서 프로젝트 루트 폴더로 이동합니다.
2. `python trading/main.py` 명령어로 프로그램을 실행합니다.
3. `API Key loading` 프롬프트가 뜨면 설정한 비밀번호를 입력합니다.
4. 실시간 로그를 확인하며 상단의 메뉴(1, 0, q)를 통해 **국내외 통합 계좌 정보 확인** 및 로그 레벨을 제어합니다.
