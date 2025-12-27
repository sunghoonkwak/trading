# 자동 거래 시스템 (KIS OpenAPI Trading System)

## 1. 목적 (Objective)
한국투자증권(KIS) OpenAPI를 활용하여 실시간 시세 조회 및 자동 매매를 수행하는 통합 트레이딩 시스템입니다. 국내 주식뿐만 아니라 **미국 주식(NASDAQ, NYSE, AMEX)의 실시간 시세 수신** 및 계좌 통합 관리가 가능합니다.

## 2. 폴더 구조 (Folder Tree)
```text
.
├── trading/                     ## 핵심 구현 폴더 (Core Implementation)
├── kis_api/                     ## KIS API 특화 패키지
│   ├── domestic_stock/          ## 국내 주식 관련 모듈 (호가, 체결, 주문)
│   ├── overseas_stock/          ## 해외 주식 관련 모듈 (호가, 체결, 공지)
│   ├── key/                     ## 보안 및 암호화 유틸리티
│   └── kis_auth.py              ## REST/WebSocket 인증 및 통신 코어 (호환성 레이어 포함)
├── main.py                      ## 엔트리 포인트 (대화형 메뉴 및 웹소켓 핸들러)
├── order_handler.py             ## 주문 실행 및 관리 로직
├── account_helper.py            ## 잔고 및 포트폴리오 조회 로직
├── trading_ui.py                ## 터미널 UI 및 컬러 로그 구현
├── trading_config.py            ## JSON 설정 로더 및 종목 정보 헬퍼
├── stock_configuration.json     ## 종목 설정 (이름, 시장, RGB 색상, 활성여부)
├── credentials.enc              ## 암호화된 API 키 저장소
├── openapi_trading.md           ## 프로젝트 문서
└── .gitignore                   ## Git 제외 설정
```

## 3. 도구 및 의존성 (Tools & Dependencies)
1. **Language**: Python 3.12+
2. **Key Libraries**:
   - `websockets`: 실시간 시세 및 체결 통보 수신
   - `pandas`: 수신 데이터 프레임화 및 가공
   - `pycryptodome`: KIS 실시간 데이터 복호화 (AES-CBC)
   - `cryptography`: API 키 암호화 보관 (Fernet)

## 4. 구현 상세 (Implementation Details)

### 1. 보안 우선 접근 (Security-First Approach)
- API 키, Secret, HTS ID는 `PBKDF2`와 `Fernet` 알고리즘으로 암호화되어 `credentials.enc` 파일에 안전하게 보관됩니다.
- 프로그램 실행 시 사용자가 입력하는 비밀번호를 통해서만 메모리에 로드됩니다.

### 2. 전역 시장 지원 (Global Market Support)
- **통합 관심종목 관리**: `stock_configuration.json` 파일에서 `KR`(국내) 및 `US`(해외) 그룹으로 종목을 통합 관리합니다.
- **동적 접두어 처리**: 미국 주식의 경우 `market` 필드(NASDAQ, NYSE, AMEX)를 자동으로 감지하여 `DNAS`, `DNYS`, `DAMS` 등의 KIS 전용 종목 코드로 변환 후 구독합니다.

### 3. 강력한 웹소켓 엔진 (Robust WebSocket Engine)
- **호완성 레이어 (Compatibility Layer)**: 공식 API 샘플 파일의 필드 정의와 실제 데이터 스트림 간의 불일치 문제를 해결하기 위해, `kis_auth.py` 내부에 `_OVERSEAS_TR_FIX` 레이어를 구현했습니다. 이를 통해 공식 파일을 수정하지 않고도 데이터 밀림 없이 정확한 파싱이 가능합니다.
- **자동 재접속**: 네트워크 연결이 끊어질 경우 지수 백오프(Exponential Backoff) 전략을 사용하여 자동으로 재접속하고 모든 종목을 재구독합니다.
- **주문 체결 통보**: 국내(`H0STCNI0`) 및 해외(`H0GSCNI0`) 주문/체결 통보를 완벽하게 지원합니다. 특히 해외 통보 데이터의 필드 밀림 현상을 자동 보정하고, 비정상적인 가격 단위(Scale)와 현지 시각(Local Time)을 추론하여 정확한 정보를 제공합니다.

### 4. 통합 해외 트레이딩 (Integrated Overseas Trading)
- **통합 주문 인터페이스**: 주문 메뉴(`2`) 진입 시 기본적으로 **해외 주식(US)**으로 설정되며, `Enter` 키를 통해 즉시 **국내 주식(KR)** 모드로 전환할 수 있습니다.
- **스마트 수량 계산**: `KRW`(국내)와 `USD`(해외) 잔고를 각각 인식하여, 현재가 대비 최대 매수 가능 수량을 자동으로 계산하여 표시합니다.
- **주문 관리 우선순위**: 주문 정정/취소(`3`) 메뉴는 **해외 미체결 내역**을 우선적으로 조회하며, 검색 결과가 없을 경우 자동으로 국내 미체결 내역을 탐색합니다.
- **결과 피드백**: 정정/취소 결과에 대해 성공 여부, 주문 번호, 처리 메시지를 명확하게 보여주며, UI 잔상을 자동으로 정리합니다.

### 5. 개선된 터미널 UI (Enhanced Terminal UI)
- **다중 레벨 컬러링**:
  - `DEBUG` (회색): 빈번한 호가 업데이트 등 배경 데이터.
  - `INFO` (종목 색상): 실제 체결 및 주문 결과 등 중요 데이터.
  - `ERROR` (빨간색): 오류 및 거부 메시지.
- **스마트 로그 고정 (Pinning)**:
  - **이중 앵커**: 동일 종목이라도 '실시간 시세(`MKT`)'와 '주문 상태(`ODR`)'를 분리하여 상단에 고정합니다. 체결 알림이 현재가 정보를 덮어쓰지 않아 두 가지 중요한 정보를 동시에 모니터링할 수 있습니다.
- **로그 정리**: 트레이딩 중 화면에 쌓인 완료된 주문/체결 로그는 메뉴에서 `c` 키를 눌러 즉시 정리할 수 있습니다.
- **실시간 로그 로테이션**: 실행 시마다 이전 로그를 타임스탬프와 함께 백업하여 `WebSocket_latest.log`를 항상 최신 상태로 유지합니다.

### 6. 대화형 포트폴리오 관리 (Interactive Portfolio Management)
- **통합 계좌 뷰 (Unified Account View)**: `f` 키를 사용하여 **요약(Summary) -> 미국 포트폴리오(US) -> 한국 포트폴리오(KR)** 순으로 뷰를 순환하며 조회할 수 있습니다.
- **개선된 리스트 UI**:
  - **페이지네이션**: 보유 종목이 많을 경우 `n` 키를 사용하여 페이지를 넘길 수 있습니다.
  - **시각적 정렬**: 한글/영문 혼용 종목명에 대해 시각적으로 완벽한 정렬(Alignment)을 지원합니다.
  - **상세 정보**: `평단가`, `현재가`, `손익금(P/L Amt)`, `수익률(P/L Rate)` 컬럼을 제공합니다.
- **스마트 분석 (Smart Analytics)**:
  - **요약 화면**: KRW/USD 각각의 총 평가액(Total Value), 주문 가능 금액(Orderable), 총 손익을 한눈에 보여줍니다.
  - **푸터(Footer)**: 각 포트폴리오 리스트 하단에 해당 시장의 보융주식 평가 총액과 합계 손익을 표시합니다.
- **데이터 정확성**: 수익률은 가중 평균 방식으로 엄격하게 계산되며, 주문 가능 금액은 별도 조회 API(`prvs_rcdl_excc_amt` 등)를 통해 검증된 값을 사용합니다.

### 7. 보안 및 개인정보 보호 (Security & Privacy)
- **자동 마스킹**: 시스템은 `App Key`, `App Secret`, `HTS ID`, `Access Token`, `Approval Key` 등 보안에 민감한 정보가 로그나 터미널에 평문으로 출력되지 않도록 **자동 마스킹(`********`)** 기능을 적용했습니다.
- **로그 안전성**: `_DEBUG` 모드를 활성화해도 통신 헤더의 보안 필드는 보호됩니다.
- **개발 규칙**: `print(headers)` 등 전체 객체를 그대로 출력하는 행위를 지양하고, 반드시 마스킹 헬퍼를 거치도록 설계되었습니다.

## 5. 논리 및 설계 구조 (Logical Structure)
- **시간대 스마트 동기화 (Timezone Smart Sync)**:
  - 기본적으로 각 시장의 **현지 시간(Local Market Time)**을 따릅니다.
  - US 시장(NASDAQ, NYSE, AMEX)의 주문 통보 시각이 누락된 경우, 자동으로 **미국 동부 표준시(EST/EDT)**로 변환하여 로그에 표시함으로써 시세 데이터 흐름과 일치시킵니다.
- **데이터 구분자 처리**: 국내(Caret `^`)와 해외(Pipe `|` 또는 Caret `^`)의 서로 다른 데이터 구분자 규격을 엔진 레벨에서 자동 판별하여 처리합니다.
- **동시성 처리 (Concurrency)**: `threading`을 통해 웹소켓 수신과 사용자 메뉴 입력을 독립적으로 처리하여 중단 없는(Non-blocking) 트레이딩 환경을 제공합니다.

## 6. 사용 방법 (How to Use)
1. 터미널에서 `python trading/main.py` 실행
2. 암호화 비밀번호 입력
3. 메뉴 선택:
   - `1`: 통합 계좌 정보 (예수금, 포트폴리오, 수익률 조회 - `f`키로 뷰 전환)
   - `2`: 주식 매수/매도 (US/KR 토글 지원)
   - `3`: 미체결 주문 정정/취소 (US 우선 조회)
   - `0`: 로그 감시 레벨 변경 (INFO <-> DEBUG)
   - `c`: 주문 로그 클리어
   - `q`: 안전하게 종료
