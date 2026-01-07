# Value Averaging (`value_averaging.py`)

이 모듈은 **다중 종목 Value Averaging** 분할매수법에 필요한 매매 계산 및 주문을 자동으로 처리합니다.

## Configuration (설정)

`value_averaging.json` 파일 구조:

```json
{
    "default_settings": {
        "duration": 200
    },
    "strategies": [
        {
            "enabled": true,
            "target": "QLD",
            "exchange": "AMEX",
            "daily_budget": 84.34,
            "target_weight_initial": 0.0325
        },
        {
            "enabled": true,
            "target": "TQQQ",
            "exchange": "NASD",
            "daily_budget": 41.68,
            "target_weight_initial": 0.016,
            "duration": 250
        }
    ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `default_settings` | obj | 모든 전략에 적용되는 기본값 |
| `strategies[]` | array | 종목별 전략 배열 |
| `enabled` | bool | 전략 활성화 여부 |
| `target` | str | 대상 종목 심볼 |
| `exchange` | str | 거래소 코드 (AMEX, NASD 등) |
| `duration` | int | 투자 기간 (일) - 개별 override 가능 |
| `daily_budget` | float | 일별 투자 예산 (자동 계산됨) |
| `target_weight_initial` | float | 초기 목표 비중 (0.0 - 1.0) |

---

## Functions (함수)

### calculate_order
당일에 매수해야 하는 주문을 계산합니다 (다중 종목 지원).

#### Strategy Logic
1. `enabled: true`인 모든 전략을 순회
2. 종목별로 `default_settings`와 병합 (전략 값이 우선)
3. 누적 목표 가치 계산: `day_count × daily_budget`
4. 금일 매수 목표액: `누적 목표 - 현재 보유 평가액`
5. 매수 수량 계산 및 **LOC 주문** 생성 (가격: 현재가 × 105%)

#### Returns
```python
{
    "status": "calculated",
    "date": "2026-01-06",
    "results": [
        {"target_ticker": "QLD", "day_count": 4, "orders": [...], ...},
        {"target_ticker": "TQQQ", "day_count": 1, "orders": [], ...}
    ],
    "total_orders": [...],  # 모든 종목의 orders 합산
    "error": None
}
```

---

### execute_orders
계산된 주문을 KIS API를 통해 실행하고 **모든 종목에 대해 히스토리를 기록**합니다.

> **Day 누적 방식**: 주문이 없어도(수량 0) 히스토리에 기록되어 day_count가 증가합니다.
> 예: 가격이 비싸서 1주도 못 살 때 → 다음날 누적분으로 2주 이상 구매 가능

> **실패 시 재시도**: `success: false`인 기록은 day_count에 포함되지 않으며, 같은 날 다시 시도할 수 있습니다.

---

## History File (히스토리 파일)

`value_averaging_history.json` - **종목별 분리 저장**:

```json
{
    "QLD": [
        {
            "date": "2026-01-06 09:08:43",
            "results": [{"ticker": "QLD", "order": {...}, "success": true, "message": "Order Placed"}],
            "success": true
        }
    ],
    "TQQQ": [
        {
            "date": "2026-01-06 09:15:18",
            "results": [{"ticker": "TQQQ", "order": null, "success": true, "message": "No order needed (insufficient qty)"}],
            "success": true
        }
    ]
}
```

히스토리는 **최신 순** (index 0이 가장 최근)으로 저장됩니다.

---

## Integration

- **Terminal UI**: `portfolio_menu` Option 3에서 호출
- **Telegram**: `/portfolio_va` 명령어에서 호출