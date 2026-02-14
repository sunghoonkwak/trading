# Value Averaging (`value_averaging.py`)

이 모듈은 **다중 종목 Value Averaging** 분할매수법에 필요한 매매 계산 및 주문을 자동으로 처리합니다.

## Configuration (설정)

`~/KIS_config/strategy_config.json` 파일 구조 (Value Averaging 섹션):

```json
{
    "value_averaging": {
        "targets": {
            "QLD": {
                "enabled": true,
                "exchange": "AMS",
                "target": 5000,
                "daily_budget": 100,
                "threshold_rate": 0.15
            },
            "TQQQ": {
                "enabled": true,
                "exchange": "NAS",
                "target": 5000,
                "daily_budget": 50,
                "threshold_rate": 0.15
            }
        }
    }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `targets` | dict | 종목별 전략 설정 딕셔너리 (Key: Ticker) |
| `enabled` | bool | 전략 활성화 여부 |
| `exchange` | str | 거래소 코드 (AMS, NAS 등) |
| `target` | float | 최대 목표 금액 (Max Target) |
| `daily_budget` | float | 일별 투자 금액 (Day Count * Daily Budget = Target Progress) |
| `threshold_rate` | float | 괴리율 임계값 (예: 0.15 = 15%). 목표 대비 차이가 이 비율 이상일 때만 주문. |

---

## Functions (함수)

### get_daily_report
당일에 매수해야 하는 주문을 계산합니다 (다중 종목 지원).

#### Strategy Logic
1. `enabled: true`인 모든 **Target**을 순회합니다.
2. **Day Count 계산**:
   - 히스토리에서 가장 최근 날짜의 기록을 확인합니다.
   - 만약 오늘 기록이 이미 존재하면(성공/스킵 불문) 그 Day Count를 유지합니다.
   - 오늘 기록이 없으면, 최근 기록의 `day_count + 1`을 사용하여 새로운 Day를 시작합니다.
4. **휴장일 체크**: `is_market_holiday("NYSE")`를 통해 휴장일 여부를 판단합니다. 휴장일인 경우 `status`를 `"market_holiday"`로 설정하고 주문 리스트를 비웁니다.
5. **목표 가치 계산**:
   - `Target Progress` = `day_count` × `daily_budget`
   - `Target Value Accumulated` = `min(target, Target Progress)` (최대 목표 금액 설정 시 캡 적용)
   - `Daily Target Amount` = `Target Value Accumulated` - `Current Value`
6. **괴리율 계산 및 주문 생성**:
   - `Divergence Rate` = `abs(Daily Target Amount) / Target Value Accumulated`
   - **주문 조건**: `Divergence Rate` >= `threshold_rate` (설정값, 기본 0.15) 인 경우에만 주문 생성.
     - **매수**: `Daily Target Amount` > 0
       - 수량 = `Daily Target Amount` / 현재가
       - 주문: 현재가 105% (LOC)
     - **매도**: `Daily Target Amount` < 0
       - 수량 = `abs(Daily Target Amount)` / 현재가
       - 주문: 시장가 (Market)
     - **Hold**: 괴리율이 `threshold_rate` 미만인 경우 주문 없음.

#### Returns
```python
{
    "status": "calculated",
    "date": "2026-02-03",
    "results": [
        {
            "target_ticker": "QLD",
            "day_count": 22,
            "orders": [...],
            "already_executed": false, # 오늘 매수 완료 여부 (스킵은 false)
            ...
        },
        ...
    ],
    "total_orders": [...],
    "error": None
}
```

---

### execute_single_order
단일 종목에 대한 주문을 KIS API를 통해 실행합니다.
- `/value_averaging`의 일괄 실행 과정에서 호출됩니다.
- LOC 주문을 생성하여 전송합니다.

### save_ticker_result
실행 결과를 `value_averaging_history.json`에 저장합니다.
- `utils.save_json(ConfigFile.VA_HISTORY, ...)`를 사용하여 날짜별/종목별로 결과를 저장하며, 주문 성공 여부와 관계없이 기록을 남깁니다.

---

## History File (히스토리 파일)

`value_averaging_history.json` - **리스트(Array) 기반 구조**:

```json
[
    {
        "date": "2026-02-06",
        "targets": {
            "QLD": {
                "day_count": 22,
                "tried_count": 1,
                "results": [
                    {
                        "time": "05:24:02",
                        "type": "buy_value_averaging",
                        "qty": 2,
                        "price": 77.09,
                        "executed": true,
                        "success": true,
                        "message": "Order Placed"
                    }
                ]
            },
            "TQQQ": { ... }
        }
    },
    ...
]
```

- **List Structure**: 최신 날짜의 기록이 리스트의 앞쪽(인덱스 0)에 위치합니다.
- **Targets Dict**: 각 날짜 항목 내에 `targets` 딕셔너리로 종목별 기록을 관리합니다.
- `executed`: 실제 주문 실행 여부. `true`면 "Already Executed"로 간주됩니다.
- `day_count`: 해당 날짜의 진행 단계. **매수 여부(Skip 포함)와 관계없이 개장일마다 증가**합니다.

---

## Integration

- **Telegram**: `/value_averaging` 명령어에서 호출 (일괄 실행 지원)
- **Terminal UI**: 실행 기능은 제거됨 (Telegram 사용 권장)

> **휴장일**: `get_daily_report()`에서 `status: "market_holiday"`를 반환하며, 이 경우 주문 실행이 차단되고 Day Count가 증가하지 않습니다. 텔레그램 리포트 하단에 휴장일 경고가 표시됩니다.