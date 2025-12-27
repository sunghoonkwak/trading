# 자동 거래 시스템 (KIS OpenAPI Trading System)

## 1. 목적
한국투자증권(KIS) OpenAPI를 활용하여 실시간 시세 조회 및 자동 매매를 수행하는 통합 트레이딩 시스템입니다. 국내 주식뿐만 아니라 **미국 주식(NASDAQ, NYSE 등)의 실시간 시세 수신** 및 계좌 통합 관리가 가능합니다.

## 2. Folder Tree
```text
.
├── trading/                     ## core implementation folder
├── kis_api/                ## KIS API specialized package
│   ├── domestic_stock/     ## 국내 주식 관련 모듈 (호가, 체결, 주문)
│   ├── overseas_stock/     ## 해외 주식 관련 모듈 (호가, 체결, 공지)
│   ├── key/                ## 보안 및 암호화 유틸리티
│   └── kis_auth.py         ## REST/WebSocket 인증 및 통신 코어 (Compatibility Layer 포함)
├── main.py                 ## 엔트리 포인트 (인터랙티브 메뉴 및 웹소켓 핸들러)
├── order_handler.py        ## 주문 실행 및 관리 로직
├── account_helper.py       ## 잔고 및 포트폴리오 조회 로직
├── trading_ui.py           ## 터미널 UI 및 컬러 로그 구현
├── trading_config.py       ## JSON 설정 로더 및 종목 정보 헬퍼
├── stock_configuration.json ## 종목 설정 (이름, 시장, RGB 색상, 활성여부)
├── credentials.enc         ## 암호화된 API 키 저장소
├── openapi_trading.md      ## 프로젝트 문서
└── .gitignore              ## Git 제외 설정
```

## 3. Tools & Dependencies
1. **Language**: Python 3.12+
2. **Key Libraries**:
   - `websockets`: 실시간 시세 및 체결 통보 수신
   - `pandas`: 수신 데이터 프레임화 및 가공
   - `pycryptodome`: KIS 실시간 데이터 복호화 (AES-CBC)
   - `cryptography`: API 키 암호화 보관 (Fernet)

## 4. Implementation Details
1. **Security-First Approach**:
   - API 키와 HTS ID는 `PBKDF2`와 `Fernet`으로 암호화되어 `credentials.enc`에 보관됩니다. 실행 시 비밀번호 입력을 통해 안전하게 로드됩니다.
2. **Global Market Support**:
   - **Unified Watchlist**: `stock_configuration.json`에서 `KR` 및 `US` 그룹으로 종목을 관리합니다.
   - **Dynamic Prefixing**: US 종목의 경우 `market` 필드(NASDAQ, NYSE, AMEX)를 참조하여 `DNAS`, `DNYS`, `DAMS` 등의 KIS 전용 접두어를 자동으로 부여하여 구독합니다.
3. **Robust WebSocket Engine**:
   - **Compatibility Layer**: 공식 샘플 파일(`asking_price.py` 등)의 필드 정의가 실제 데이터 스트림과 일치하지 않는 문제를 `kis_auth.py` 내부의 수정 레이어(`_OVERSEAS_TR_FIX`)로 해결했습니다. 공식 파일을 수정하지 않고도 데이터 밀림 없이 정확한 파싱이 가능합니다.
   - **Automatic Reconnection**: 네트워크 단절 시 지수 백오프(Exponential Backoff) 전략을 사용하여 자동으로 재접속 및 전 종목 재구독을 수행합니다.
   - **Order Notification**: 국내(`H0STCNI0`) 및 해외(`H0GSCNI0`) 주문/체결 통보를 완벽 지원합니다. 특히 해외 통보의 경우 필드 밀림 현상을 자동 보정하고, 비정상적인 가격 단위(Scale)와 현지 시각(Local Time)을 추론하여 사용자에게 정확한 정보를 제공합니다.
4. **Integrated Overseas Trading**:
   - **Unified Place Order Interface**: 주문 메뉴(`2`) 진입 시 기본적으로 **해외 주식(US)**으로 설정되며, `Enter` 키를 통해 즉시 **국내 주식(KR)** 모드로 전환할 수 있습니다.
   - **Smart Quantity Calculation**: `KRW`(국내)와 `USD`(해외) 잔고를 각각 인식하여, 현재가 대비 최대 매수 가능 수량을 자동으로 계산하여 표시합니다.
   - **Prioritized Order Management**: 주문 정정/취소(`3`) 메뉴는 **해외 미체결 내역**을 우선적으로 조회하며, 검색 결과가 없을 경우 자동으로 국내 미체결 내역을 탐색합니다.
   - **Result Feedback**: 정정/취소 결과에 대해 성공 여부, 주문 번호, 처리 메시지를 명확하게 피드백하며, UI 잔상을 자동으로 정리합니다.

5. **Enhanced Terminal UI**:
   - **Multi-Level Coloring**:
     - `DEBUG` (회색): 빈번한 호가 업데이트 등 배경 데이터.
     - `INFO` (종목 색상): 실제 체결 및 주문 결과 등 중요 데이터.
     - `ERROR` (빨간색): 오류 및 거부 메시지.
   - **Smart Log Pinning**:
     - **Dual Anchor**: 동일 종목이라도 '실시간 시세(`MKT`)'와 '주문 상태(`ODR`)'를 분리하여 상단에 고정합니다. 이로 인해 체결 알림이 현재가 정보를 덮어쓰지 않아 두 가지 중요한 정보를 동시에 모니터링할 수 있습니다.
   - **Clear Command**: 트레이딩 중 화면에 쌓인 완료된 주문/체결 로그는 메뉴에서 `c` 키를 눌러 즉시 정리하고 시세 모니터링에 집중할 수 있습니다.
   - **Real-time Log Rotation**: 실행 시마다 이전 로그를 타임스탬프와 함께 백업하여 `WebSocket_latest.log`를 항상 깨끗하게 유지합니다.

6. **Interactive Portfolio Management**:
   - **Unified Account View**: A single interface cycles through **Summary -> US Portfolio -> KR Portfolio** using the `f` key, providing smooth navigation between asset classes.
   - **Enhanced List UI**:
     - Supports pagination for large portfolios using the `n` key.
     - Features visually perfect alignment for mixed English/Korean stock names.
     - Includes detailed columns: `Average Price`, `Current Price`, `P/L Amount`, and `P/L Rate`.
   - **Smart Analytics**:
     - **Summary**: Displays Total Value (Stock Eval + Orderable), Orderable Cash, and P/L Summary for both KR and US markets.
     - **Footer**: Each portfolio view concludes with a **Total Line** showing the specific market's Total Stock Evaluation and Aggregate P/L.
   - **Data Accuracy**: Uses strictly calculated weighted averages for P/L rates and verifies `Orderable Cash` through dedicated balance inquiries.

7. **Security & Privacy (로그 보안)**:
    - **Automatic Masking**: 시스템은 `App Key`, `App Secret`, `HTS ID`, `Access Token`, `Approval Key` 등 보안에 민감한 정보가 로그나 터미널에 평문으로 출력되지 않도록 **자동 마스킹(`********`)** 기능을 포함하고 있습니다.
    - **Log Safety**: `_DEBUG` 모드 활성 시에도 통신 헤더의 보안 필드는 보호됩니다.
    - **Safety Rule**: 개발 시 `print(headers)` 등 전체 객체를 그대로 출력하는 행위를 지양하고, 반드시 마스킹 헬퍼를 거치도록 설계되었습니다.

## 5. 논리 및 설계 구조 (Logical Structure)
- **Timezone Smart Sync**:
  - 기본적으로 각 시장의 **현지 시간(Local Market Time)**을 따릅니다.
  - US 시장(NASDAQ, NYSE, AMEX)의 주문 통보 시각이 누락된 경우, 자동으로 **미국 동부 표준시(EST/EDT)**로 변환하여 로그에 표시, 시세 데이터 흐름과 일치시킵니다.
- **Data Delimiters**: 국내(Caret `^`)와 해외(Pipe `|` 또는 Caret `^`)의 서로 다른 데이터 구분자 규격을 엔진 레벨에서 자동 판별하여 처리합니다.
- **Concurrency**: `threading`을 통해 웹소켓 수신과 사용자 메뉴 입력을 독립적으로 처리하여 중단 없는 트레이딩 환경을 제공합니다.

## 6. How to Use
1. 터미널에서 `python trading/main.py` 실행
2. 암호화 비밀번호 입력
3. 메뉴 선택:
   - `1`: 통합 계좌 정보 (예수금, 포트폴리오, 수익률 조회)
   - `2`: 주식 매수/매도 (US/KR 토글 지원)
   - `3`: 미체결 주문 정정/취소 (US 우선 조회)
   - `0`: 로그 감시 레벨 변경 (INFO <-> DEBUG)
   - `c` / `q`: 로그 클리어 / 안전하게 종료
