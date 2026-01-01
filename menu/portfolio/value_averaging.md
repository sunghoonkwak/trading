# value_averaging.md

이 모듈은 Value Averaging 분할매수법에 필요한 매매 계산 및 주문을 자동으로 처리하는 모듈입니다.

## Purpose (목적)

Value Averaging 분할매수법에 필요한 매매 계산 및 주문을 자동으로 처리하는 모듈입니다.

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
    "target": "QLD",
    "exchange": "AMEX",
    "duration": 120,
    // "sell_profit": 0.10
}
```

| Field | Type | Description |
|-------|------|-------------|
| `target` | str | 대상 종목 심볼 |
| `exchange` | str | 거래소 코드 (AMEX, NASD 등) |
| `duration` | int | 투자 기간 (일) |

## Functions (기능)

### load_config
`value_averaging.json` 파일에서 설정을 로드합니다.

#### Returns
- `dict`: 설정 정보

---

### calculate_order
당일에 매수 주문해야하는 가격/수량을 계산합니다.

#### Strategy Logic
1. `load_config()`를 통해서 설정 정보를 로드합니다.
2. 초기 실행(`history` 없음) 시 `daily_budget`을 계산하고 설정 파일에 저장합니다.
   - `daily_budget` = (총 자산 가치 × 목표 비중) / 투자 기간(`duration`)
3. `target_value_accumulated`(누적 목표 가치)를 계산합니다.
   - `accumulated` = 투자 일수(`day_count`) × `daily_budget`
4. `daily_target_amount`(금일 매수 목표액)를 계산합니다.
   - `target_amt` = `target_value_accumulated` - 현재 보유 평가액
5. **매수 주문 생성**:
   - `daily_target_amount`가 0보다 클 경우 매수 수량(`qty`)을 계산합니다.
   - **주문 유형**: LOC (Limit-On-Close)
   - **주문 가격**: 현재가의 110% (`current_price * 1.1`), 소수점 2자리 반올림.
   - *목표 달성 시(매수 목표액 < 0) 주문을 생성하지 않습니다.*

#### Returns
- `dict`: 당일 매수 주문 정보

---

### build_value_averaging_report
현재 Value Averaging 상태를 조회합니다. Terminal UI와 Telegram 모두에서 사용됩니다.

#### Returns
- `dict`: 다음 키 중 하나 포함
  - `executed_today`: 오늘 모든 주문이 성공한 경우 히스토리 데이터
  - `current_result`: 실패한 주문이 있어 재시도가 필요하거나 새로 계산된 주문 정보
  - `is_retry` (bool): 히스토리의 실패 주문을 다시 시도하는 경우 `True`

---

### execute_orders
계산된 주문을 KIS API를 통해 실행합니다.

#### Args
- `orders` (list): 주문 리스트
- `config` (dict): 설정 정보

#### Returns
- `list`: 각 주문의 실행 결과 (`success`, `type`, `error` 포함)

---

### save_history
주문 실행 성공 시 당일의 전략 상태를 `value_averaging_history.json`에 저장합니다.

#### Args
- `order_data` (dict): 당일 주문 및 전략 데이터

#### Returns
- `bool`: 저장 성공 여부 (오늘 날짜의 기록이 이미 있으면 실패 기록을 성공으로 업데이트함)

---

### show_history_viewer
`value_averaging_history.json`에 저장된 과거 기록을 테이블 형식으로 조회합니다.

#### Navigation
| Key | Action |
|-----|--------|
| `f` | 다음 5개 항목 |
| `g` | 첫 페이지로 이동 |
| `q` | 메뉴로 돌아가기 |

*참고: 실패(`success: false`)한 주문은 히스토리 뷰어 테이블에 표시되지 않습니다.*

---

### value_averaging_menu
Value Averaging 전략의 메인 컨트롤러입니다.

#### Features
- **유연한 재시도**: 오늘 실행 기록이 있더라도 실패한 주문이 남아 있다면 `Execute` 메뉴를 통해 언제든 다시 시도할 수 있습니다.
- **모듈화**: `build_value_averaging_report()`, `execute_orders()` 등을 호출하여 기능을 수행합니다.


## History File (히스토리 파일)

`value_averaging_history.json` 구조:

```json
{
    "history": [
       {
            "date": "2026-01-01",
            "state": "holding",
            "config": {
                "target": "QLD",
                "exchange": "AMEX",
                "duration": 40,
            },
            "holdings": {
                "qty": 9,
                "avg_price": 43.17,
                "cur_price": 0.0
            },
            "daily_budget": 150.0,
            "orders": [
                {
                    "type": "buy_guaranteed",
                    "price": 47.06,
                    "qty": 2,
                    "order_type": "LOC",
                    "type_code": "34",
                    "desc": "Buy at 109% of avg (guaranteed)",
                    "success": false,
                    "error": "APBK0918 - 장운영시간이 아닙니다.(단,주간거래시간이면 전용화면 주문가능, 주문시간 외 불가)"
                },
                {
                    "type": "buy_lower",
                    "price": 43.17,
                    "qty": 1,
                    "order_type": "LOC",
                    "type_code": "34",
                    "desc": "Buy at 100% of avg (lower cost)",
                    "success": false,
                    "error": "APBK0918 - 장운영시간이 아닙니다.(단,주간거래시간이면 전용화면 주문가능, 주문시간 외 불가)"
                }
            ],
            "error": null
        },
    ]
}
```

히스토리는 **최신 순** (index 0이 가장 최근)으로 저장됩니다.