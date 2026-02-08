# KIS 실시간 트레이딩 시스템 (KIS Real-time Trading System)

이 프로젝트는 **한국투자증권(KIS) API**를 활용한 실시간 트레이딩 시스템입니다.
**웹 기반 이벤트 뷰어(Event Viewer)**와 **터미널 메뉴(Terminal Menu)**를 결합하여 모니터링과 제어를 동시에 수행할 수 있습니다.

## ✨ 주요 기능

- **자동 초기화 (Automated Startup)**: 실행 시 텔레그램, KIS API, 웹 서버가 자동으로 초기화됩니다.
- **웹 이벤트 뷰어 (Web Event Viewer)**:
  - 실시간 주문(Orders), 시세(Quotes), 메모(Memos), 시스템 로그(System Logs)를 WebSocket으로 모니터링합니다.
  - 현대적인 다크 모드 UI와 효율적인 화면 분할(좌우 5:5)을 제공합니다.
  - 접속 주소: `http://<서버IP>:8080`
- **전략 (Strategies)**:
  - **RAOEO (Unlimited Buying)**: 다중 종목(Multi-Target) 동시 운영 지원 (예: SOXL, FAS 등), 개별 설정 및 휴장일 자동 대응.
  - **Value Averaging**: 목표 비중 기반 분할 매수/매도 전략.
- **터미널 제어 인터페이스 (Terminal Control)**:
  - Docker 환경에 최적화되어, 인터랙티브 메뉴 대신 **웹 대시보드**와 **텔레그램**을 주 제어 수단으로 사용합니다.
- **실시간 알림 및 원격 제어**: 텔레그램 봇을 통해 매매 알림을 받고 명령어로 조회/주문이 가능합니다.
- **도커 지원 (Dockerized)**: 컨테이너 환경에서 손쉽게 배포 및 실행이 가능합니다.

## 🚀 시작하기

### 필수 요구사항
- **Python 3.9+** (직접 실행 시)
- Docker & Docker Compose (Docker 실행 시 선택 사항)
- **설정 파일** (`~/KIS_config/` 디렉토리 또는 볼륨 마운트 필요):

### 📁 외부 설정 디렉토리 (`~/KIS_config/`)
모든 민감한 설정 파일은 프로젝트 외부에 저장됩니다. `templete/` 디렉토리에 있는 예제 파일들을 `~/KIS_config/`로 복사하여 설정할 수 있습니다:
```
~/KIS_config/
├── kis_devlp.yaml            # KIS API 설정 (모의/실전)
├── credentials.enc           # 암호화된 API 키
├── service-account.json      # Google Sheets 서비스 계정
├── telegram.txt              # 텔레그램 봇 토큰/채팅 ID (옵션)
├── portfolio.json            # 캐싱된 포트폴리오 데이터
├── portfolio_weights.json    # 포트폴리오 비중 설정
├── raoeo.json                # RAOEO 전략 설정 (Config)
├── raoeo_history.json        # RAOEO 매매 히스토리
├── value_averaging.json      # Value Averaging 설정
├── value_averaging_history.json # Value Averaging 히스토리
└── memo.json                 # 텔레그램 메모 저장소
```

### 설치 및 실행

1. **Docker로 실행 (권장)**
   환경 설정 없이 바로 실행할 수 있는 가장 간편한 방법입니다. `docker compose` 명령어를 사용합니다.
   ```bash
   # 데몬 모드(백그라운드)로 빌드 및 실행
   docker compose up -d --build

   # 로그 확인
   docker logs -f my-trading-bot
   ```
   *참고: Docker 모드에서는 터미널 메뉴가 비활성화되며 자동으로 데몬 모드로 전환됩니다.*

2. **Python 직접 실행 (고급 사용자)**
   개발 목적으로 소스 코드를 직접 수정하며 실행할 때 적합합니다.
   ```bash
   # 1. 가상환경 활성화 (선택 사항)
   source venv/bin/activate

   # 2. 필수 라이브러리 설치
   # Linux
   pip install -r requirements.txt
   # Windows
   # pip install -r requirements-windows.txt

   # 3. 실행 (src 디렉토리의 main.py 실행)
   # PYTHONPATH 설정 필요할 수 있음
   python src/main.py
   ```

## 📱 Telegram 봇 명령어

🤖 **Trading Bot Initialized**

| 명령어 | 설명 |
| :--- | :--- |
| **포트폴리오 (Portfolio)** | |
| `/portfolio` | Portfolio check (interactive) |
| `/portfolio_weight` | Rebalancing suggestions |
| `/placed_orders` | Show open orders |
| **전략 (Strategy)** | |
| `/raoeo` | RAOEO status & order |
| `/value_average` | Value Averaging order |
| **기타 (Misc)** | |
| `/daily_report [date]` | View past reports |
| `/memo` | View recent memos (1 week) |

## 🕹️ 사용 방법

### 1. 웹 대시보드 (Web Dashboard)
- **접속**: 브라우저에서 `http://localhost:8080` (또는 서버 IP) 접속.
- **구성 (5:5 분할 레이아웃)**:
  - **좌측 (50%)**:
    - **Orders**: 실시간 체결 및 접수 내역 (상단)
    - **Quotes**: 실시간 호가/시세 변동 (중단)
    - **Memos**: 최근 기록된 메모 내역 (하단)
  - **우측 (50%)**:
    - **System Log**: 시스템 상태 및 에러 로그 (자동 줄바꿈 지원)

### 2. 터미널 메뉴 (비활성화됨)
Docker 환경에서는 인터랙티브 터미널 메뉴가 사용되지 않습니다. 모든 제어는 **웹 대시보드** 또는 **텔레그램 봇**을 통해 수행하십시오.

## 📂 프로젝트 구조

```
.
├── src/                        # 소스 코드 디렉토리
│   ├── main.py                 # 진입점 (시스템 초기화 및 메인 루프)
│   ├── web_server.py           # FastAPI 웹 서버 (WebSocket & API)
│   ├── display.py              # 로그 메시지 및 터미널 출력 처리
│   ├── thread_comm.py          # 스레드 간 IPC 통신 관리
│   ├── thread_state.py         # 시스템 스레드 상태 추적
│   ├── trading_config.py       # 트레이딩 관련 설정 로더
│   ├── trading_state.py        # 실시간 매매 상태 관리
│   ├── kis/                    # KIS API 연동 모듈
│   │   ├── wrapper.py          # KIS API 통합 래퍼 (주문/시세)
│   │   ├── kis_thread.py       # KIS 실시간 데이터 수신 스레드
│   │   ├── event_handler.py    # KIS 이벤트 처리 및 배포
│   │   ├── event_pipe.py       # 레거시 IPC 파이프 (유지보수용)
│   │   └── kis_api/            # 저수준 KIS REST/WebSocket API
│   ├── strategy/               # 매매 전략 로직
│   │   ├── raoeo.py            # 무한 매수 (RAOEO) 전략
│   │   └── value_averaging.py  # 밸류 에버리징 (VA) 전략
│   ├── portfolio/              # 포트폴리오 및 잔고 관리
│   ├── telegram_bot/           # 텔레그램 봇 (모듈화된 핸들러)
│   │   ├── telegram_bot.py     # 메인 봇 인스턴스 및 라우팅
│   │   ├── telegram_portfolio.py # 포트폴리오 관련 명령 처리
│   │   └── ... (기타 모듈)
│   ├── scheduler/              # 스케줄러 (보고서 생성 등 자동 작업)
│   ├── data/                   # 데이터 저장 및 로컬 DB 관리
│   ├── web/                    # 프론트엔드 (HTML/JS/CSS)
│   └── utils.py                # 공용 유틸리티 함수
├── Dockerfile                  # 도커 빌드 설정
├── docker-compose.yml          # 도커 컴포즈 설정
├── requirements.txt            # 파이썬 의존성
└── README.md                   # 프로젝트 문서
```

## ⚠️ 참고 사항
- **터미널 출력**: 모든 시스템 알림은 터미널에도 출력됩니다. 하지만 메뉴 조작 중 출력이 섞일 수 있으므로 **웹 뷰어** 확인을 권장합니다.
- **로그 파일**: `WebSocket_latest.log`에 모든 로그가 저장되며, 실행 시마다 `logs/` 디렉토리로 백업(Rotation)됩니다.
