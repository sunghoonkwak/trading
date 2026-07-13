# Runtime State Adapter (`src/infrastructure/system_state.py`)

KIS worker/WebSocket과 Telegram bot의 런타임 상태를 스레드 안전하게 관리하는
인프라 어댑터입니다. KIS REST가 필요한 포트폴리오 조회는 `is_kis_ready()`로
가능 여부를 판단합니다.

```python
from infrastructure.system_state import ThreadStatus, update_kis_state

update_kis_state(thread_status=ThreadStatus.RUNNING)
```
