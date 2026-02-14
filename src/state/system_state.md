# System State Manager (`src/state/system_state.py`)

애플리케이션 내 다양한 스레드(KIS, Telegram 등)의 생명주기와 인증 상태를 관리하는 중앙 모듈입니다.

# Core Logic (핵심 로직)

1. **상태 추적**: 각 스레드의 실행 상태(Running, Stopped, Error)와 KIS API 인증 상태를 독립적으로 추적합니다.
2. **스레드 안전성**: `threading.Lock`을 사용하여 여러 스레드에서 동시에 상태를 조회하거나 업데이트할 때 발생할 수 있는 데이터 경합을 방지합니다.
3. **싱글톤 패턴**: `SystemStateManager` 클래스는 시스템 전체에서 단 하나의 인스턴스만 존재하도록 보장하여 상태 일관성을 유지합니다.

# Key Functions (주요 함수)

## `update_kis` / `update_telegram`
각각 KIS 스레드와 텔레그램 스레드의 상태 정보를 업데이트합니다.

- **입력 (Input)**: `**kwargs` (업데이트할 필드와 값)

## `get_kis` / `get_telegram`
현재의 상태 객체(`KISState`, `TelegramState`)를 반환합니다.

# Configuration (None)

# Usage Example (사용 예시)

```python
from state.system_state import SystemStateManager, ThreadStatus

manager = SystemStateManager()
manager.update_kis(thread_status=ThreadStatus.RUNNING)
```
