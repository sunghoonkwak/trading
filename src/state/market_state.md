# Market State Manager (`src/state/market_state.py`)

실시간 시장 데이터(주가, 호가, 거래량 등)를 관리하고 데이터의 무결성을 보장하며 디스크 영속성을 관리하는 고급 상태 관리 모듈입니다.

# Core Logic (핵심 로직)

1. **싱글톤 인스턴스**: 시스템 전체에서 단일 인스턴스를 유지하여 마켓 데이터의 일관성을 보장합니다.
2. **데이터 유효성 검사**: 업데이트 시 주가, 호가, 거래량 등의 수치가 유효한지(양수 여부 등) 검증하여 비정상적인 데이터 유입을 방지합니다.
3. **스레드 안전성**: `threading.Lock`을 사용하여 다중 스레드 환경에서 데이터 경합 없이 안전하게 읽고 쓸 수 있습니다.
4. **디스크 영속성 (Persistence)**: 실시간 데이터를 60초마다 `stock_data.json`에 저장하며, 재시작 시 5분 이내의 최신 데이터인 경우 자동으로 복구합니다.

# Key Functions (주요 함수)

## `update_ticker`
종목 코드와 데이터 딕셔너리를 받아 유효성 검사 후 상태를 업데이트합니다.

## `get_ticker` / `get_price`
특정 종목의 전체 데이터 또는 현재가만을 안전하게 가져옵니다.

## `save_to_disk` / `load_from_disk`
현재의 메모리 상태를 파일로 저장하거나 파일로부터 복구합니다.

# Configuration (None)

# Usage Example (사용 예시)

```python
from state.market_state import get_market_manager

manager = get_market_manager()

# 데이터 업데이트
manager.update_ticker("SOXL", {"price": 35.5, "vol": 1000})

# 가격 조회
current_price = manager.get_price("SOXL")
```
