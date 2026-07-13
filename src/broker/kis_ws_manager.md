# KIS WebSocket Manager Compatibility Surface (`src/broker/kis_ws_manager.py`)

이 모듈은 `infrastructure.kis.kis_ws_manager`의 forwarding-only compatibility
surface입니다. 실제 WebSocket 연결과 구독 동작은 destination sidecar인
`src/infrastructure/kis/kis_ws_manager.md`를 참고합니다.

## Compatibility Consumer (호환 소비자)

`broker.kis_worker`와 KIS stop-timeout compatibility test가 `WSManager`를
가져오기 위해 이 모듈을 사용합니다. 새 production consumer를 추가하지
않습니다.

## Usage Example (사용 예시)

```python
from infrastructure.kis.kis_ws_manager import WSManager

ws = WSManager()
ws.initialize()
```
