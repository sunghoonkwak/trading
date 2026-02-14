# Data Service (`data_service.py`)

`data_service.py`는 애플리케이션의 **데이터 중앙 공급소** 역할을 하는 핵심 모듈입니다.
UI 모듈(`portfolio.py`, `handle_account_info.py`)과 데이터 소스(`KIS Thread`, `Portfolio File`) 사이의 중계자 역할을 수행합니다.

## Purpose (목적)

1. **Centralized Access**: 모든 데이터 요청을 이 모듈로 단일화하여 데이터 흐름을 추적하고 관리하기 쉽게 합니다.
2. **Caching**: 무분별한 API 호출을 방지하기 위해 데이터를 메모리 및 파일(`portfolio.json`)에 캐싱합니다.
3. **Data Unification**: KIS API의 국내/해외 잔고 데이터와 환율 정보 등을 하나의 통일된 구조로 병합하여 제공합니다.
4. **Resilience**: 시세 정보 누락 시 WebSocket이나 추가 API 호출을 통해 데이터를 자동 보정합니다.

## Key Functions (핵심 기능)

### `get_portfolio_data(force_refresh=False)`
전체 포트폴리오 데이터를 조회하는 메인 함수입니다.

- **Caching Logic**:
    - 메모리 캐시 유효(기본 5분) 시 캐시 반환.
    - `force_refresh=True` 또는 캐시 만료 시 `KIS Thread`에 요청 전송.
    - `KIS Thread` 응답 대기 및 수신 후 `portfolio.json` 저장 및 캐시 갱신.
    - **GSheet/KIS 에러 시**: `metadata`에 `gsheet_error` 또는 `kis_error`가 있으면 **캐시하지 않음** (불완전한 데이터 재사용 방지).
- **Data Processing**:
    - `merged_data`: 국내/해외 종목을 티커 키 기반으로 통합.
    - `stats`: 국가별 자산 총액, 비중, 현금 비중 등 통계 계산.
    - `targets`: `portfolio_weights.json` 기반 목표 비중 계산.

### `get_weight_diffs()`
현재 포트폴리오와 목표 비중 간의 차이를 분석하여 리밸런싱 정보를 계산합니다.

- **Group Constituents Handling**:
    - `portfolio_weights.json`의 그룹 설정에서 `constituents`를 추출합니다.
    - Constituents의 보유비중은 `main_ticker`에 합산되어 표시됩니다.
    - Constituents는 리포트에서 개별적으로 표시되지 않습니다.
- **Weight Calculation**: `calculate_weights.py` 로직을 통해 목표 비중 산출 (F&G 지수 기반 현금 배분).
- **Qty Calculation**: (목표 금액 - 현재 금액) / 현재가.
- **Smart Price Fetching**:
    - 보유하지 않은 종목(수량 0)이라도 `qty_diff`를 계산하기 위해 가격을 조회합니다.
    - **1순위**: 보유 종목의 현재가 (`merged_data`)
    - **2순위**: 실시간 WebSocket 시세 (`menu.raoeo.get_current_price`)
    - **3순위**: KIS API 조회 (국내 `inquire_price` / 해외 `fetch_price`)

## Data Structure (`portfolio.json`)

`get_portfolio_data()`가 반환하고 파일로 저장하는 데이터의 구조입니다.

```json
{
  "merged_data": {
    "AAPL": {
      "qty": 10,
      "cur_price": 150.0,
      "current_value_usd": 1500.0,
      "type": "STOCK",
      "currency": "USD",
      ...
    },
    "005930": { ... }
  },
  "stats": {
    "us_stock_usd": ...,
    "kr_stock_krw": ...,
    "execution_rate": ...
  },
  "targets": {
    "AAPL": 0.15,
    "QQQ": 0.20
  },
  "metadata": {
    "exchange_rate": 1300.5
  }
}
```

## Dependencies
- **Source**: `kis.kis_thread` (API communication)
- **Calculation**: `calculate_weights.py` (Target weights)
- **Config**: `~/KIS_config/portfolio_weights.json` (Rebalancing rules)
- **Cache**: `~/KIS_config/portfolio.json` (Cached portfolio data)
