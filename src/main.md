# Trading System Main (`src/main.py`)

KIS 자동매매 시스템의 진입점(Entry Point)입니다. 
전체적인 시스템 초기화, `src/core/` 패키지에 포함된 핵심 서비스 기동, 그리고 안정적인 실행을 위한 메인 루프를 관리합니다.

# Core Logic (핵심 로직)

1. **로깅 및 환경 설정**: `LogManager`와 `core.trading_config`를 통해 로그 설정 및 종목 데이터를 로드합니다.
2. **시스템 기동 (`run`)**: 다음 순서로 각 서브시스템을 초기화합니다.
   - **텔레그램 봇**: 원격 제어 및 상태 보고용 독립 스레드.
   - **KIS 엔진**: `kis.kis_thread`를 통한 REST 인증 및 실시간 WebSocket 파이프라인 구축.
   - **백그라운드 스케줄러**: `scheduler` 패키지를 통한 정기적 매매 업무 실행.
   - **웹 대시보드**: `core.web_server`를 통한 실시간 이벤트 뷰어 제공.
3. **데몬 모드**: 시스템이 종료되지 않도록 메인 스레드에서 무한 대기하며, 종료 시 모든 리소스를 안전하게 해제(`shutdown`)합니다.

# Key Functions (주요 함수)

## `TradingSystem.run`
시스템의 전체 시작 프로세스를 실행합니다. 각 서비스는 독립된 스레드에서 기동됩니다.

## `TradingSystem.shutdown`
KIS 웹소켓 중단, 텔레그램 세션 종료 등 모든 리소스를 순차적으로 해제합니다.

# Usage Example (사용 예시)

```bash
# 프로젝트 루트 디렉토리에서 실행
python src/main.py
```
