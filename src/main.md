# Trading System Main (`src/main.py`)

KIS/Toss 자동매매 시스템의 진입점(Entry Point)입니다.
전체적인 시스템 초기화와 application/infrastructure/interface adapter의
composition root 역할, 그리고 안정적인 실행을 위한 메인 루프를 관리합니다.

## Core Logic (핵심 로직)

1. **로깅 및 환경 설정**: `infrastructure.logger.LogManager`와 `infrastructure.trading_configuration`를 통해 로그 설정 및 종목 데이터를 로드합니다.
2. **시스템 기동 (`run`)**: Docker 컨테이너 시작 시에는 Telegram과
   Event Viewer control plane만 초기화합니다. 실제 trading runtime은
   Telegram `/system_on` 명령을 받은 뒤 시작합니다.
   - **텔레그램 봇**: 원격 제어 및 상태 보고용 독립 스레드. 초기화에
     실패하면 거래 런타임을 시작하지 않습니다.
   - **KIS 엔진**: `infrastructure.kis.worker`를 통한 REST 인증 및 실시간 WebSocket 파이프라인 구축.
     `KIS_ENABLE_REST_API=false`이면 REST 인증은 건너뛰고 WebSocket 인증과
     구독 초기화만 수행합니다.
   - **Toss API**: `infrastructure.toss.auth.ensure_daily_token()`으로 당일 Toss access
     token을 준비합니다. KIS 초기화 뒤, 스케줄러와 웹 대시보드 시작 전에
     수행되며 실패하면 Telegram 알림을 시도한 뒤 자동 실행 표면을
     시작하지 않습니다.
   - **백그라운드 스케줄러**: `interfaces.scheduler` adapter를 통한 정기적
     매매 업무 실행. portfolio use case는 `main.py`에서 주입합니다.
   - **웹 대시보드**: `interfaces.web` adapter를 통한 실시간 이벤트 뷰어 제공.
     Docker 시작 직후에도 접속 가능하지만, runtime OFF 상태에서는 외부
     API나 주문/스케줄 실행으로 이어지는 요청이 차단됩니다.
3. **데몬 모드**: 시스템이 종료되지 않도록 메인 스레드에서 무한 대기하며,
   `/system_off`는 Telegram은 유지한 채 KIS/WebSocket/scheduler runtime을
   중지합니다. 프로세스 종료 시 모든 리소스를 안전하게 해제(`shutdown`)합니다.

## Key Functions (주요 함수)

## HTTP Timeout Defaults
`infrastructure.http_defaults.install_requests_default_timeout()`을 시작 시 호출하여
`requests` 기반 외부 API 호출에 30초 기본 timeout을 적용합니다. 호출자가
개별 요청에 `timeout`을 명시하면 그 값이 우선합니다. 이 설정은 KIS, Toss,
Telegram 등 런타임 프로세스 안의 `requests` 호출이 무기한 대기하는 것을
막기 위한 의도적인 전역 기본값입니다.

### `TradingSystem.run`
컨테이너의 시작 프로세스를 실행합니다. Telegram bot과 web Event Viewer를
초기화하고 `application.runtime_service.RuntimeController`를 Telegram
factory에 주입한 뒤 daemon loop에 진입합니다. Docker 시작 직후 trading
runtime 상태는 OFF입니다.

### `TradingSystem.start_trading_runtime`
Telegram `/system_on` 명령에서 호출됩니다. GSheet cache, KIS, Toss 인증,
미체결 주문 동기화, scheduler 순서로 trading runtime을 시작합니다. 주문
동기화는 Toss 인증 구성 이후에 실행되어 KIS·Toss 주문을 함께 조회합니다.
Web dashboard는 이미 control plane으로 떠 있으므로 중복 시작하지 않습니다. KIS 또는 Toss
초기화 실패 시 Telegram 알림을 시도하고 runtime을 OFF로 유지하지만,
Telegram/web control plane과 컨테이너 프로세스는 계속 살아 있습니다.

`tests/core/test_runtime.py`는 fake collaborators로 이 순서와 KIS/Toss
실패 시 scheduler/web을 시작하지 않는 fail-closed lifecycle smoke를
검증합니다. 이 smoke는 네트워크 또는 주문 변경 호출을 하지 않습니다.

### `TradingSystem.stop_trading_runtime`
Telegram `/system_off` 명령에서 호출됩니다. Scheduler와 KIS/WebSocket
runtime을 중지하고 Telegram bot은 유지합니다. 이미 OFF 상태인 경우에도
성공으로 응답하는 idempotent 명령입니다.

### Web control surface while OFF
Web dashboard process는 한 번 시작되면 컨테이너 생존 동안 유지될 수 있지만,
trading runtime이 OFF이면 외부 API나 주문/스케줄 실행으로 이어지는 web
요청은 차단됩니다. 차단 대상은 WebSocket `sync_orders`,
`/api/orders/{order_id}/cancel`, `/api/trigger/portfolio`,
`/api/trigger/order`, `/api/holdings/{ticker}`입니다. 정적 페이지와 메모
조회/삭제는 runtime OFF 상태에서도 허용됩니다.

### `TradingSystem.initialize_kis`
KIS worker thread를 시작하고, 설정에 따라 REST 인증을 수행한 뒤 WebSocket
approval key와 실시간 이벤트 파이프라인을 초기화합니다.
`KIS_ENABLE_REST_API=false`이면 REST 인증은 건너뛰지만 WebSocket 인증과
구독 초기화는 계속 수행합니다. KIS 초기화가 실패하면 이후 Toss,
스케줄러, 웹 대시보드 단계로 진행하지 않고 Telegram 알림을 시도합니다.

### `TradingSystem.initialize_toss`
Toss 토큰 파일을 확인하고, 당일 유효 토큰이 없거나 만료 safety margin 안에
있으면 새 토큰을 발급해 저장합니다.

### `TradingSystem.shutdown`
KIS 웹소켓 중단, 텔레그램 세션 종료 등 모든 리소스를 순차적으로 해제합니다.

## Usage Example (사용 예시)

```bash
# Docker 환경 내부에서 실행되거나 docker-compose 로 실행되어야 합니다.
# 로컬 호스트에서의 직접 실행(python src/main.py)은 충돌 방지를 위해 차단되어 있습니다.
docker compose up -d --build
```
