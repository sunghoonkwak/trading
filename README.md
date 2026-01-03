# 🚀 KIS Real-time Auto Trading System

## 1. 개요 (Overview)
본 프로젝트는 **한국투자증권(KIS) OpenAPI**를 기반으로 한 통합 트레이딩 솔루션입니다. 국내 및 미국 주식 전용 실시간 시세 조회, 정밀한 자동 매매, 그리고 **RAOEO(무한매수법)** 전략을 터미널 UI와 **Telegram**을 통해 언제 어디서나 제어할 수 있도록 설계되었습니다.

---

## 2. 주요 기능 (Key Features)

### 💎 프리미엄 UI/UX
- **ANSI Terminal UI**: 별도의 GUI 없이도 화려하고 직관적인 컬러 터미널 인터페이스를 제공합니다.
- **Event Viewer (Dual Terminal)**: 메인 상호작용 화면과 분리된 별도의 터미널에서 실시간 로그(WebSocket)를 모니터링합니다. **Named Pipe** 통신과 **Windows Mutex** 기반의 프로세스 감지로 안정적인 재실행을 보장합니다.
- **Smart Alerts**: 백그라운드 작업 및 Telegram 명령 결과를 메인 UI 알림 영역에 실시간으로 브로드캐스팅합니다.

### 📈 트레이딩 & 전략
- **RAOEO Strategy**: 무한매수법 자동화 모듈. 실패한 주문에 대한 **지능형 재시도(Retry)** 및 히스토리 관리 기능을 포함합니다.
- **Unified Portfolio**: 국내/대외 자산을 통합하여 자산 구성, 국가별 비중, 목표 대비 리밸런싱 수량을 자동으로 계산합니다.
- **Real-time Sync**: 웹소켓을 통한 체결 통지 즉시 UI와 데이터가 동기화됩니다.

### 📱 Telegram 원격 제어
- **Remote Reporting**: 외출 중에도 `/raoeo_report`, `/portfolio` 명령으로 현재 상태를 즉시 확인합니다.
- **Remote Execution**: 계산된 주문을 `/raoeo_order`, `/portfolio_va` 명령으로 즉시 실행할 수 있습니다.
- **Security**: 모든 메시지는 **HTML 모드**로 전송되어 레이아웃이 깨지지 않으며, 스레드 안정성을 보장합니다.

### 🛡️ 보안 및 안정성
- **AES Credentials**: API 키와 민감 정보를 암호화하여 저장하며, 기동 시 비밀번호 인증을 거칩니다.
- **Token Manager**: 1시간 버퍼 기반의 자동 토큰 갱신 로직으로 세션 끊김 없는 끊김 없는 거래를 보장합니다.

---

## 3. 폴더 구조 (Project Structure)

```text
.
├── main.py                     # Entry point (로그 로테이션, 웹소켓 관리)
├── event_viewer.py             # 별도 터미널 로그 뷰어 (Named Pipe 방식)
├── display.py                  # ANSI UI 렌더링 엔진 (Thread-safe alerts)
├── thread_comm.py              # 스레드 간 통신 (Queue) 정의
├── thread_state.py             # 스레드 공유 상태 관리
├── menu/                       # 대화형 메뉴 시스템
│   ├── menu.py                 # 메인 메뉴 허브
│   ├── raoeo/                  # [Strategy] RAOEO 무한매수법 전담 모듈
│   ├── portfolio/              # [Strategy] 포트폴리오 UI 및 연동
│   └── handle_*.py             # 계좌/주문/관리 각 섹션 핸들러
├── telegram_bot/               # Telegram 봇 통합 패키지
├── kis/                        # KIS OpenAPI Core & Threading
│   ├── kis_api/                # KIS SDK (인증, 주문, 시세 등)
│   ├── kis_thread.py           # API 전담 백그라운드 스레드
│   ├── event_pipe.py           # Named Pipe 로그/데이터 전송
│   └── event_handler.py        # 실시간 웹소켓 이벤트 처리
├── data/                       # 데이터 서비스 계층
│   ├── data_service.py         # 포트폴리오 데이터 캐싱 및 중앙 관리
│   └── portfolio.json          # 캐싱된 포트폴리오 데이터
├── exports/                    # 엑셀 내보내기 파일 저장 디렉토리
├── logs/                       # 애플리케이션 로그 파일 디렉토리
├── stock_configuration.json    # 종목별 UI 설정
├── telegram.txt                # 텔레그램 봇 토큰/채팅 ID
└── credentials.enc             # 암호화된 인증 데이터
```

---

## 4. 시작하기 (Quick Start)

### ⚙️ 환경 설정
1. 의존성 패키지를 설치합니다.
```bash
pip install -r requirements.txt
```
2. `kis_api/key/generate_credentials.py`를 실행하여 API 키를 암호화 저장합니다.
3. 프로젝트 루트에 `telegram.txt` 파일을 생성하고 텔레그램 토큰과 채팅 ID를 입력합니다.
```
BOT_TOKEN,CHAT_ID
```

### 🚀 실행
```bash
python main.py
```
1. 선택한 메뉴에 따라 거래를 시작합니다.
   - `r` : RAOEO 전략판 진입
   - `p` : 통합 포트폴리오 분석
   - `1~3` : 기본 자산 관리 및 주문

---

## 5. Telegram 명령어 가이드

| Command | Category | Description |
|---------|----------|-------------|
| `/raoeo_report` | RAOEO | 오늘 매매 대상 종목 및 현재 전략 상태 조회 |
| `/raoeo_order` | RAOEO | 계산된 RAOEO 주문 즉시 실행 및 히스토리 저장 |
| `/portfolio` | Portfolio | 대화형 포트폴리오 조회 (종목 상세 버튼) |
| `/portfolio_weight` | Portfolio | 목표 비중 대비 리밸런싱 제안 목록 |
| `/portfolio_va` | Portfolio | Value Averaging 주문 계산 및 실행 (Yes/No 확인) |
| `/memo` | Memo | 최근 1주일 저장된 메모 조회 |

---
*각 모듈의 상세 설명은 해당 디렉토리 내 `.md` 파일을 참조하십시오.*
