# Market State Manager (`src/state/market_state.py`)

실시간 시세 데이터 관리 및 데이터 영속성(Persistence)을 담당하는 모듈입니다.

# Core Logic (핵심 로직)

1. **실시간 데이터 관리**: WebSocket을 통해 수신된 최신 주가, 호가, 거래량 등의 정보를 메모리에 저장합니다.
2. **영속성 관리**: 60초마다 메모리 내의 실시간 데이터를 `stock_data.json` 파일에 저장하여, 시스템 재시작 시 빠른 데이터 복구를 지원합니다.
3. **데이터 보호**: `Lock`을 통해 데이터 업데이트와 파일 저장 간의 동기화를 보장합니다.

# Key Functions (주요 함수)

## `update_ticker`
특정 종목의 시세 정보를 업데이트합니다. 첫 데이터 수신 시 백그라운드 저장 스레드를 자동으로 시작합니다.

## `load_from_disk` / `save_to_disk`
파일로부터 데이터를 로드하거나 현재 상태를 파일로 저장합니다. 로드 시 5분이 경과된 오래된 데이터는 무시합니다.

# Configuration (None)

# Usage Example (사용 예시)

```python
from state.market_state import MarketStateManager

manager = MarketStateManager()
manager.update_ticker("SOXL", {"price": 35.5})
```
