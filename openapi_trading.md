# 자동 거래 시스템 (KIS OpenAPI Trading System)

## 1. 목적
한국투자증권(KIS) OpenAPI를 활용하여 실시간 시세 조회 및 자동 매매를 수행하는 시스템입니다. 현재는 실시간 국내 주식 체결가(H0STCNT0) 수신 및 보안 인증 체계가 구현되어 있습니다.

## 2. Folder tree
```text
.
├── trading/                     ## core implementation folder
│   ├── key/                    ## encryption & security utilities
│   │   ├── key.py              ## 중심 키 유도 및 복호화 로직 (Password based)
│   │   ├── generate_credentials.py
│   │   └── validate_credentials.py
│   ├── main.py                 ## entry point script (WebSocket start)
│   ├── kis_auth.py             ## REST API/WebSocket 인증 및 통신 라이브러리 (KISClient 역할 통합)
│   ├── rebalance.py            ## (WIP) 매매 로직
│   ├── target_weight.json      ## (WIP) 목표 포트폴리오 비중
│   └── openapi_trading.md      ## 프로젝트 문서
├── credentials.enc             ## 암호화된 API 키 저장소 (보안 유지 필수)
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
   - `App Key`, `App Secret`, 그리고 **`HTS ID`**는 `PBKDF2`와 `Fernet`을 사용하여 암호화된 `credentials.enc` 파일에 저장됩니다.
   - 실행 시 사용자가 입력하는 비밀번호를 통해 `key.py`의 `get_secrets_from_password()` 함수가 동적으로 복호화하여 메모리에 로드합니다.
2. **Authentication & Token Management**:
   - `kis_auth.py`에서 REST용 Access Token과 WebSocket용 Approval Key를 관리합니다.
   - 토큰은 `~/steven/KIS_config` 경로에 날짜별로 캐싱되어 불필요한 API 호출을 최소화합니다.
   - `_DEBUG = True` 설정을 통해 인증 과정을 트래킹할 수 있습니다.
3. **Real-time Data (WebSocket)**:
   - `KISWebSocket` 클래스를 통해 비동기적으로 실시간 시세를 수신합니다.
   - `PINGPONG` 핸들링 및 암호화된 데이터의 실시간 AES 복호화가 구현되어 있습니다.
   - `main.py`에서 구독할 종목 리스트(`stocks_to_watch`)를 설정하여 즉시 모니터링이 가능합니다.
4. **Interactive Operation**:
   - `main.py` 실행 시 웹소켓이 활성화된 후 `menu(ws)` 함수를 호출하여 사용자로부터 명령을 입력받거나 시스템을 종료하는 로직이 추가되었습니다.
5. **Data Processing**:
   - 수신된 실시간 체결 데이터는 `pandas.DataFrame`으로 변환되어 가공 및 분석이 용이합니다.
