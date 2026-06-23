# Runtime State Manager (`src/state/system_state.py`)

KIS worker/WebSocket과 Telegram bot의 런타임 상태를 관리하는 작은 모듈입니다.
Toss API는 상주 스레드가 없고 호출부에서 토큰 준비와 API 오류를 직접 처리하므로
이 상태 매니저에 별도 상태를 보관하지 않습니다.

## Core Logic (핵심 로직)

1. **KIS 상태 추적**: worker thread, REST 인증, WebSocket 인증, WebSocket 연결 상태를 추적합니다.
   `data_service`는 `is_kis_ready()`를 사용해 KIS 포트폴리오 조회 가능 여부를 판단합니다.
2. **Telegram 상태 추적**: Telegram bot thread 시작 여부와 연결 상태를 기록합니다.
2. **스레드 안전성**: `threading.Lock`을 사용하여 여러 스레드에서 동시에 상태를 조회하거나 업데이트할 때 발생할 수 있는 데이터 경합을 방지합니다.
3. **싱글톤 패턴**: `SystemStateManager` 클래스는 시스템 전체에서 단 하나의 인스턴스만 존재하도록 보장하여 상태 일관성을 유지합니다.

## Key Functions (주요 함수)

### `update_kis_state` / `update_telegram_state`
모듈 레벨 helper로 각각 KIS 스레드와 텔레그램 스레드의 상태 정보를 업데이트합니다.
클래스 인스턴스를 직접 사용할 때는 `SystemStateManager.update_kis()`와
`SystemStateManager.update_telegram()`을 호출할 수 있습니다.

- **입력 (Input)**: `**kwargs` (업데이트할 필드와 값)

### `is_kis_ready`
KIS worker가 실행 중이고 REST 인증이 완료된 경우에만 `True`를 반환합니다.
KIS REST가 필요한 포트폴리오 조회의 실행 게이트로 사용됩니다.

## Configuration (None)

## Usage Example (사용 예시)

```python
from state.system_state import ThreadStatus, update_kis_state

update_kis_state(thread_status=ThreadStatus.RUNNING)
```
