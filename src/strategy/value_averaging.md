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

### get_daily_report
당일에 매수해야 하는 주문을 계산합니다 (다중 종목 지원).

#### Strategy Logic
1. `enabled: true`인 모든 전략을 순회합니다.
2. 종목별로 `default_settings`와 병합합니다.
3. **Day Count 계산**:
   - 히스토리에서 가장 최근 날짜의 기록을 확인합니다.
   - 만약 오늘 기록이 이미 존재하면(성공/스킵 불문) 그 Day Count를 유지합니다.
   - 오늘 기록이 없으면, 최근 기록의 `day_count + 1`을 사용하여 새로운 Day를 시작합니다.
4. **휴장일 체크**: `is_market_holiday("NYSE")`를 통해 휴장일 여부를 판단합니다. 휴장일인 경우 `status`를 `"market_holiday"`로 설정하고 주문 리스트를 비웁니다.
5. 누적 목표 가치 계산: `day_count × daily_budget`
5. **괴리율 계산 및 주문 생성 (15% 임계값)**:
   - **매수**: `현재 평가금` < `누적 목표` * 0.85 (85% 미만) 인 경우
     - 수량 = (누적 목표 - 현재 평가금) / 현재가
     - 주문: 현재가 100% (LOC)
   - **매도**: `현재 평가금` > `누적 목표` * 1.15 (115% 초과) 인 경우
     - 수량 = (현재 평가금 - 누적 목표) / 현재가
     - 주문: 시장가 (Market)
   - 그 외(±15% 이내): 주문 없음 (Hold)

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
- `/portfolio_va`의 순차 처리 과정에서 호출됩니다.
- LOC 주문을 생성하여 전송합니다.

### save_ticker_result
실행 결과를 `value_averaging_history.json`에 저장합니다.
- 날짜별/종목별로 결과를 저장하며, 주문 성공 여부와 관계없이 기록을 남깁니다.

---

## History File (히스토리 파일)

`value_averaging_history.json` - **날짜 기반 구조**:

```json
{
    "QLD": {
        "2026-02-02": {
            "day_count": 21,
            "tried_count": 1,
            "results": [
                {
                    "time": "09:30:00",
                    "type": "skip",
                    "executed": false,
                    "success": true,
                    "message": "Skipped"
                }
            ]
        },
        "2026-02-03": {
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
        }
    }
}
```

- **Date Key**: 날짜(YYYY-MM-DD)를 키로 사용하여 하루의 기록을 그룹화합니다.
- `executed`: 실제 주문 실행 여부. `true`면 "Already Executed"로 간주됩니다. (단, **Skip**은 실행으로 간주하지 않아 재평가 가능)
- `day_count`: 해당 날짜의 진행 단계. **매수 여부(Skip 포함)와 관계없이 개장일마다 증가**합니다.

---

## Integration

- **Telegram**: `/portfolio_va` 명령어에서 호출 (순차 실행 지원)
- **Terminal UI**: 실행 기능은 제거됨 (Telegram 사용 권장)

> **휴장일**: `get_daily_report()`에서 `status: "market_holiday"`를 반환하며, 이 경우 주문 실행이 차단되고 Day Count가 증가하지 않습니다. 텔레그램 리포트 하단에 휴장일 경고가 표시됩니다.