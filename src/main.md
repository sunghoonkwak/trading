# Trading System Main (`src/main.py`)

KIS/Toss 자동매매 시스템의 진입점(Entry Point)입니다.
전체적인 시스템 초기화, `src/core/` 패키지에 포함된 핵심 서비스 기동, 그리고 안정적인 실행을 위한 메인 루프를 관리합니다.

## Core Logic (핵심 로직)

1. **로깅 및 환경 설정**: `LogManager`와 `core.trading_config`를 통해 로그 설정 및 종목 데이터를 로드합니다.
2. **시스템 기동 (`run`)**: 다음 순서로 각 서브시스템을 초기화합니다.
   - **텔레그램 봇**: 원격 제어 및 상태 보고용 독립 스레드.
   - **KIS 엔진**: `broker.kis_worker`를 통한 REST 인증 및 실시간 WebSocket 파이프라인 구축.
     `KIS_ENABLE_REST_API=false`이면 REST 인증은 건너뛰고 WebSocket 인증과
     구독 초기화만 수행합니다.
   - **Toss API**: `toss.auth.ensure_daily_token()`으로 당일 Toss access
     token을 준비합니다. KIS 초기화 뒤, 스케줄러와 웹 대시보드 시작 전에
     수행되며 실패하면 자동 실행 표면을 시작하지 않습니다.
   - **백그라운드 스케줄러**: `scheduler` 패키지를 통한 정기적 매매 업무 실행.
   - **웹 대시보드**: `core.web_server`를 통한 실시간 이벤트 뷰어 제공.
3. **데몬 모드**: 시스템이 종료되지 않도록 메인 스레드에서 무한 대기하며, 종료 시 모든 리소스를 안전하게 해제(`shutdown`)합니다.

## Key Functions (주요 함수)

## Global Timeout Monkey-Patch
`requests` 모듈의 기본 호출 로직을 전향적으로 오버라이드(Monkey-Patching)하여 외부 API 통신 지연으로 인해 스케줄러나 메인 스레드가 무한 대기에 빠지는 현상을 완전히 방지합니다. 기본적으로 30초의 타임아웃을 강제 적용합니다.

### `TradingSystem.run`
시스템의 전체 시작 프로세스를 실행합니다. KIS와 Toss 초기화가 모두
성공한 뒤 스케줄러와 웹 대시보드를 기동합니다.

### `TradingSystem.initialize_kis`
KIS worker thread를 시작하고, 설정에 따라 REST 인증을 수행한 뒤 WebSocket
approval key와 실시간 이벤트 파이프라인을 초기화합니다.
`KIS_ENABLE_REST_API=false`이면 REST 인증은 건너뛰지만 WebSocket 인증과
구독 초기화는 계속 수행합니다. KIS 초기화가 실패하면 이후 Toss,
스케줄러, 웹 대시보드 단계로 진행하지 않습니다.

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
