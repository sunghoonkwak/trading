# raoeo.md

이 모듈은 라오어 무한 매수법에 필요한 매매 계산 및 주문을 자동으로 처리하는 모듈입니다.

## Purpose (목적)

라오어 무한 매수법에 필요한 매매 계산 및 주문을 자동으로 처리하는 모듈입니다.

## Menu Options (메뉴 옵션)

| Key | Action | Description |
|-----|--------|-------------|
| `1` | Execute Orders | 주문 계산 및 실행 |
| `2` | View History | 누적 히스토리 조회 (Pagination) |
| `q` | Quit | 이전 메뉴로 돌아가기 |

## Configuration (설정)

`raoeo.json` 파일 구조:

```json
{
    "seed": 1000,
    "target": "SOXL",
    "exchange": "AMEX",
    "duration": 40,
    "sell_profit": 0.10
}
```

| Field | Type | Description |
|-------|------|-------------|
| `seed` | int | 총 투자 금액 (USD) |
| `target` | str | 대상 종목 심볼 |
| `exchange` | str | 거래소 코드 (AMEX, NASD 등) |
| `duration` | int | 투자 기간 (일) |
| `sell_profit` | float | 매도 수익률 (0.10 = 10%) |

## Functions (기능)

### load_config
`raoeo.json` 파일에서 설정을 로드합니다.

#### Returns
- `dict`: 설정 정보

---

### calculate_order
당일에 매수/매도 주문해야하는 가격/수량을 계산합니다.

#### Strategy Logic
1. `load_config()`를 통해서 설정 정보를 로드합니다.
2. `fetch_overseas_balance()`를 통해서 현재 보유중인 target 주식의 평단가를 확인합니다.
3. **매도**: 평단가 × (1 + sell_profit) 가격으로 보유한 주식 전체를 매도합니다.
4. **매수**: 당일 사용가능한 자금 (seed/duration)을 아래와 같이 분배합니다.

| State | Price | Ratio | Description |
|-------|-------|-------|-------------|
| Initial (보유 없음) | 현재가 × 110% | 100% | LOC 매수 |
| Holding (보유 중) | 평단가 × (sell_profit - 1%) | 50% | 자전거래 방지 LOC |
| Holding (보유 중) | 평단가 × 100% | 50% | 평단가 하락용 LOC |

#### Returns
- `dict`: 당일 매수/매도 주문 정보

---

### build_raoeo_report
현재 RAOEO 상태를 조회합니다. Terminal UI와 Telegram 모두에서 사용됩니다.

#### Returns
- `dict`: 다음 키 중 하나 포함
  - `executed_today`: 오늘 이미 실행된 경우 히스토리 데이터
  - `current_result`: 새로 계산된 주문 정보

---

### execute_orders
계산된 주문을 KIS API를 통해 실행합니다.

#### Args
- `orders` (list): 주문 리스트
- `config` (dict): 설정 정보

#### Returns
- `list`: 각 주문의 실행 결과 (`success`, `order` 포함)

---

### save_history
주문 실행 성공 시 당일의 전략 상태를 `raoeo_history.json`에 저장합니다.

#### Args
- `order_data` (dict): 당일 주문 및 전략 데이터

#### Returns
- `bool`: 저장 성공 여부

---

### show_history_viewer
`raoeo_history.json`에 저장된 과거 기록을 테이블 형식으로 조회합니다.

#### Navigation
| Key | Action |
|-----|--------|
| `f` | 다음 5개 항목 |
| `g` | 첫 페이지로 이동 |
| `q` | 메뉴로 돌아가기 |

---

### raoeo_menu
라오어 전략의 메인 컨트롤러입니다.

#### Features
- **중복 방지**: 금일 이미 주문을 실행했다면 실행 메뉴 진입 시 경고와 함께 실행을 제한합니다.
- **모듈화**: `build_raoeo_report()`, `execute_orders()` 등을 호출하여 기능을 수행합니다.

## Telegram Integration

이 모듈의 함수들은 Telegram 봇에서도 사용됩니다:

| Telegram Command | Function Called |
|------------------|-----------------|
| `/raoeo_report` | `build_raoeo_report()` |
| `/raoeo_order` | `execute_orders()`, `save_history()` |

## History File (히스토리 파일)

`raoeo_history.json` 구조:

```json
{
    "history": [
        {
            "date": "2025-12-31",
            "state": "holding",
            "config": { ... },
            "holdings": { "qty": 6, "avg_price": 43.74, "cur_price": 44.10 },
            "orders": [ ... ]
        }
    ]
}
```

히스토리는 **최신 순** (index 0이 가장 최근)으로 저장됩니다.