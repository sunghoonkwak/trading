# KIS 실시간 트레이딩 시스템 (KIS Real-time Trading System)

이 프로젝트는 **한국투자증권(KIS) API**를 활용한 실시간 트레이딩 시스템입니다.
**웹 기반 이벤트 뷰어(Event Viewer)**와 **터미널 메뉴(Terminal Menu)**를 결합하여 모니터링과 제어를 동시에 수행할 수 있습니다.

## ✨ 주요 기능

- **자동 초기화 (Automated Startup)**: 실행 시 텔레그램, KIS API, 웹 서버가 자동으로 초기화됩니다.
- **웹 이벤트 뷰어 (Web Event Viewer)**:
  - 실시간 주문(Orders), 시세(Quotes), 시스템 로그(System Logs)를 WebSocket으로 모니터링합니다.
  - 현대적인 다크 모드 UI와 효율적인 화면 분할(좌우 7:3)을 제공합니다.
  - 접속 주소: `http://<서버IP>:8080`
- **터미널 제어 인터페이스 (Terminal Control)**:
  - **Super Menu**: 시스템 상태 모니터링 및 스레드 관리.
  - **Trading Menu**: 수동 매매, 잔고 조회, 미체결 주문 관리 등 실질적 기능 제공.
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
├── kis_devlp.yaml               # KIS API 설정 (모의/실전)
├── password.txt                 # 복호화 비밀번호
├── credentials.enc              # 암호화된 API 키
├── telegram.txt                 # 텔레그램 봇 토큰/채팅 ID
├── service-account.json         # Google Sheets 서비스 계정
├── portfolio.json               # 캐싱된 포트폴리오 데이터
├── portfolio_weights.json       # 포트폴리오 비중 설정
├── raoeo.json                   # RAOEO 전략 설정 (Config)
├── raoeo_history.json           # RAOEO 매매 히스토리
├── value_averaging.json         # Value Averaging 설정
├── value_averaging_history.json # Value Averaging 히스토리
└── memo.json                    # 텔레그램 메모 저장소
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

   # 3. 실행
   python main.py
   ```

## 📱 Telegram 봇 명령어

텔레그램을 통해 시스템 상태를 확인하고 전략을 실행할 수 있습니다.

| 명령어 | 설명 |
| :--- | :--- |
| **전략 (Strategy)** | |
| `/raoeo` | **RAOEO 전략** 상태를 조회하고 매수 주문을 실행합니다. (성공/실패 내역, 예산 표시) |
| `/portfolio_va` | **Value Averaging** 전략을 실행합니다. 순차적으로 주문 실행 여부를 결정하며, **Skip된 종목**도 수동으로 재검토할 수 있습니다. |
| **포트폴리오 (Portfolio)** | |
| `/portfolio` | 현재 잔고 요약을 조회하고, 버튼을 눌러 개별 종목 상세 정보를 확인합니다. |
| `/portfolio_weight` | 현재 비중과 목표 비중을 비교하여 **리밸런싱**이 필요한 종목을 제안합니다. |
| `/placed_orders` | 현재 미체결된 주문 내역(Open Orders)을 조회합니다. |
| **기타 (Misc)** | |
| `/memo` | 메모를 저장하거나 확인합니다. (일반 텍스트 전송 시 자동 저장) |
| `/cancel` | 진행 중인 대화형 세션(Portfolio, RAOEO 등)을 취소하고 종료합니다. |

## 🕹️ 사용 방법

### 1. 웹 대시보드 (Web Dashboard)
- **접속**: 브라우저에서 `http://localhost:8080` (또는 서버 IP) 접속.
- **구성 (7:3 분할 레이아웃)**:
  - **좌측 (70%)**:
    - **Orders**: 실시간 체결 및 접수 내역 (상단)
    - **Quotes**: 실시간 호가/시세 변동 (하단)
  - **우측 (30%)**:
    - **System Log**: 시스템 상태 및 에러 로그 (자동 줄바꿈 지원)

### 2. 터미널 메뉴 (Terminal Menu)
- **Trading Menu**: 초기화 완료 후 자동으로 진입합니다. (직접 실행 시에만 유효)
  - `1`: 잔고 확인 (Account Info)
  - `2`: 수동 주문 (Place Order)
  - `3`: 미체결 내역 및 정정/취소 (Manage Orders)
  - `r`: RAOEO 메뉴
  - `p`: 포트폴리오 메뉴
  - `q`: 시스템 종료 (Exit System)

## 📂 프로젝트 구조

```
.
├── main.py                 # 진입점 (자동 초기화 및 모듈 조정)
├── web_server.py           # FastAPI 웹 서버 (WebSocket 스트리밍)
├── display.py              # 알림 및 로그 처리 (터미널 출력 활성화)
├── web/                    # 프론트엔드 리소스
│   ├── index.html          # 대시보드 HTML
│   └── static/             # CSS & JS
├── menu/                   # 메뉴 하위 모듈
│   ├── menu.py             # 트레이딩 메뉴 로직
│   └── portfolio/          # 포트폴리오 관련 (VA 등)
├── telegram_bot/           # 텔레그램 봇 핸들러
│   ├── telegram_bot.py     # 봇 초기화 및 에러 핸들링
│   ├── telegram_raoeo.py   # RAOEO 커맨드
│   └── telegram_portfolio.py # 포트폴리오 커맨드
├── scheduler/              # 스케줄러 (자동 실행 작업)
└── data/                   # 데이터 처리
```

## ⚠️ 참고 사항
- **터미널 출력**: 모든 시스템 알림은 터미널에도 출력됩니다. 하지만 메뉴 조작 중 출력이 섞일 수 있으므로 **웹 뷰어** 확인을 권장합니다.
- **로그 파일**: `WebSocket_latest.log`에 모든 로그가 저장되며, 실행 시마다 `logs/` 디렉토리로 백업(Rotation)됩니다.
