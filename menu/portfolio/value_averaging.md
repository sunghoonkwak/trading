# Value Averaging (`value_averaging.py`)

이 모듈은 Value Averaging 분할매수법에 필요한 매매 계산 및 주문을 자동으로 처리합니다.

## Purpose (목적)

장기 적립식 투자를 위한 Value Averaging 전략을 구현합니다. 매일 누적 목표 가치에 도달하기 위해 필요한 매수량을 계산하고 LOC 주문을 생성합니다.

## Configuration (설정)

`value_averaging.json` 파일 구조:

```json
{
    "target": "QLD",
    "exchange": "AMEX",
    "duration": 120,
    "daily_budget": 150.0,
    "target_weight_initial": 0.05
}
```

| Field | Type | Description |
|-------|------|-------------|
| `target` | str | 대상 종목 심볼 |
| `exchange` | str | 거래소 코드 (AMEX, NASD 등) |
| `duration` | int | 투자 기간 (일) |
| `daily_budget` | float | 일별 투자 예산 (자동 계산됨) |
| `target_weight_initial` | float | 초기 목표 비중 (0.0 - 1.0) |

## Functions (함수)

### load_config / save_config
`value_averaging.json` 설정 파일을 읽고 씁니다.

---

### load_history / save_history
`value_averaging_history.json` 히스토리 파일을 읽고 씁니다.

---

### calculate_order
당일에 매수해야 하는 주문을 계산합니다.

#### Args
| Arg | Type | Description |
|-----|------|-------------|
| `targets` | dict | 티커별 목표 비중 `{ticker: weight}` |
| `price_map` | dict | 티커별 현재가 `{ticker: price}` |
| `merged_portfolio` | dict | 병합된 포트폴리오 데이터 |
| `total_value_usd` | float | 총 자산 가치 (USD) |
| `exchange_rate` | float | USD/KRW 환율 (필수) |

#### Strategy Logic
1. `load_config()`로 설정 로드
2. `targets`에서 목표 비중, `price_map`에서 현재가 조회 (없으면 `fetch_price` 폴백)
3. 초기 실행 시 `daily_budget` 계산: `(총자산 × 목표비중) / duration`
4. 누적 목표 가치 계산: `day_count × daily_budget`
5. 금일 매수 목표액: `누적 목표 - 현재 보유 평가액`
6. 매수 수량 계산 및 **LOC 주문** 생성 (가격: 현재가 × 110%, 소수점 2자리)

#### Returns
```python
{
    "status": "calculated",
    "date": "2026-01-01",
    "target_ticker": "QLD",
    "day_count": 5,
    "daily_budget": 150.0,
    "target_value_accumulated": 750.0,
    "current_value": 600.0,
    "daily_target_amount": 150.0,
    "current_price": 85.50,
    "target_weight": 0.05,
    "orders": [...],
    "error": None
}
```

---

### execute_orders
계산된 주문을 KIS API를 통해 실행합니다.

#### Args
- `order_report` (dict): `calculate_order()`의 반환값

#### Returns
- `list`: 각 주문의 실행 결과 (`order`, `success`, `message` 포함)

---

## History File (히스토리 파일)

`value_averaging_history.json` 구조:

```json
{
    "history": [
        {
            "date": "2026-01-01",
            "success": true,
            "orders": [
                {
                    "type": "buy_value_averaging",
                    "ticker": "QLD",
                    "qty": 2,
                    "price": 94.05,
                    "order_type": "LOC"
                }
            ]
        }
    ]
}
```

히스토리는 **최신 순** (index 0이 가장 최근)으로 저장됩니다.

## Integration

- **Terminal UI**: `portfolio_menu` Option 3에서 호출
- **Telegram**: `/portfolio_va` 명령어에서 호출