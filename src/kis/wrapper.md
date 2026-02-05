# KIS Wrapper (`kis/wrapper.py`)

## 개요
이 모듈은 KIS API의 고수준 래퍼(Wrapper) 역할을 수행하며, 주문 관리, 시세 조회, 그리고 주문 동기화 기능을 제공합니다. 기존 `menu` 기능과 `kis/price.py` 로직이 통합되었습니다.

## 주요 기능

### 1. 주문 동기화 (Order Synchronization)
API와 로컬 상태 간의 주문 내역을 동기화합니다.
- **`SyncManager`**: 디바운싱(Debouncing)을 통해 불필요한 API 중복 호출을 방지합니다.
- **`sync_open_orders()`**: 한국/미국 미체결 주문을 조회하여 로컬 메모리 및 UI에 반영합니다.

### 2. 시세 조회 (Price Fetching)
- **`fetch_price(ticker, exchange=None)`**:
  - 해외 주식의 현재가를 조회합니다.
  - 거래소 코드가 없으면 `trading_config`를 통해 자동 매핑합니다.
  - 다양한 필드(`last`, `base`, `prpr` 등)를 확인하여 장중/장외 가격을 유연하게 가져옵니다.

### 3. 주문 관리 (Order Management)
- **`fetch_open_orders()`**: 한국(`KR`) 및 미국(`US`) 미체결 내역을 통합된 DataFrame으로 반환합니다.
- **`execute_manage_action(market, action_type, order_data, new_price)`**:
  - 주문 정정(`01`) 및 취소(`02`)를 실행합니다.
  - 시장 구분(KR/US)에 따라 적절한 API를 호출합니다.

## 사용 예시
```python
from kis.wrapper import request_sync, fetch_price

# 현재가 조회
price = fetch_price("AAPL")

# 주문 동기화 요청 (비동기/디바운싱 적용)
request_sync()
```
