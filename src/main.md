# Trading System Main (`src/main.py`)

KIS 자동매매 시스템의 진입점(Entry Point)입니다. 
전체적인 시스템 초기화, 각 서비스 스레드 기동, 그리고 안정적인 실행을 위한 메인 루프를 관리합니다.

# Core Logic (핵심 로직)

1. **초기화 (`setup_logging`)**: 로깅 환경을 설정하고 기존 로그를 아카이빙합니다.
2. **시스템 기동 (`run`)**: 다음 순서로 각 서브시스템을 초기화합니다.
   - 텔레그램 봇: 알림 및 명령 수신용.
   - KIS API: REST 인증 및 실시간 웹소켓 연결.
   - 스케줄러: 정해진 시간에 매매 로직 실행.
   - 웹 서버: 실시간 모니터링 대시보드 제공.
3. **데몬 모드**: 시스템이 종료되지 않도록 메인 스레드에서 무한 대기하며, 종료 시 모든 리소스를 안전하게 해제합니다.

# Key Functions (주요 함수)

## `TradingSystem.run`
시스템의 전체 시작 프로세스를 실행합니다.

## `TradingSystem.shutdown`
모든 스레드와 네트워크 연결을 순차적으로 중지합니다.

# Configuration (`KIS_config/`)
사용자의 인증 정보 및 전략 설정 파일을 로드하기 위해 `~/KIS_config` 경로를 참조합니다.

# Usage Example (사용 예시)

```python
from main import TradingSystem

if __name__ == "__main__":
    app = TradingSystem()
    app.run()
```
