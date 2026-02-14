# RAOEO Strategy (`raoeo.py`)

이 모듈은 라오어 무한 매수법에 필요한 매매 계산 및 주문을 자동으로 처리하는 모듈입니다.

## Purpose (목적)

라오어 무한 매수법에 필요한 매매 계산 및 주문을 자동으로 처리하는 모듈입니다.

## Configuration (설정)

`~/KIS_config/strategy_config.json` 파일 구조 (RAOEO 섹션):

```json
{
    "raoeo": {
        "targets": {
            "SOXL": {
                "seed": 1000,
                "exchange": "AMS",
                "duration": 40,
                "sell_profit": 0.10
            },
            "FAS": {
                "seed": 1000,
                "exchange": "AMS",
                "duration": 40,
                "sell_profit": 0.10
            }
        }
    }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `targets` | dict | 대상 종목별 설정 딕셔너리 (Key: Ticker) |
| `seed` | int | 총 투자 금액 (USD) |
| `exchange` | str | 거래소 코드 (**AMS**, **NYS**, **NAS** 필수) |
| `duration` | int | 투자 기간 (일) |
| `sell_profit` | float | 매도 수익률 (0.10 = 10%) |

## Functions (기능)

### load_config
`raoeo.json` 파일에서 설정을 로드합니다.

#### Returns
- `dict`: `targets` 키를 포함한 설정 정보

---

### calculate_orders
모든 타겟 종목에 대해 당일 매수/매도 주문을 계산합니다.

#### Strategy Logic
1. `load_config()`로 설정을 로드하고 `targets` 내의 각 종목을 순회합니다.
2. 각 종목별로:
    - `fetch_price()`를 통해 현재가와 보유 정보를 조회합니다.
    - **Phase 판단**: 소모금액(평단가 × 보유량) 기준으로 3단계 분류.
    - **매도**: 보유량 > 1이면 `(보유량 - 1)`의 50%씩 지정가/LOC 매도.
    - **매수**: Phase에 따라 주문 분배.

**매수 전략 (3단계)**:

| Phase | Condition | Price | Qty | Type (ID) | Description |
|-------|-----------|-------|-----|-----------|-------------|
| Phase 0 | 소모금액 < seed×10% | 평단가 × (1 + sell_profit - 0.01) | 일일구매량 100% (최소1) | `buy_phase0_main` | LOC 매수 |
| Phase 0 | 소모금액 < seed×10% | 평단가 × 95% | seed10%수량 - 보유수량 - 일일구매량 | `buy_phase0_fill` | LOC 10% 채움 (0이하 생략) |
| Phase 1 | seed×10% ≤ 소모금액 < seed/2 | 평단가 × (1 + sell_profit - 0.01) | 일일구매량 100% (최소1) | `buy_phase1` | LOC 매수 |
| Phase 2 | 소모금액 ≥ seed/2 | 평단가 × 100% | 일일구매량 50% (최소1) | `buy_phase2_avg` | LOC 평단가 매수 |
| Phase 2 | 소모금액 ≥ seed/2 | 평단가 × (1 + sell_profit - 0.01) | 일일구매량 50% (최소1) | `buy_phase2_upper` | LOC 110% 매수 |

**매도 전략**:

| Condition | Price | Qty | Type (ID) | Description |
|-----------|-------|-----|-----------|-------------|
| 보유량 > 1 | 평단가 × (1 + sell_profit) | (보유량-1)의 50% (홀수 포함) | `sell_limit` | 지정가 익절 |
| 보유량 > 1 | 평단가 × (1 + sell_profit) | (보유량-1)의 50% | `sell_loc` | LOC 익절 |

#### Returns
- `dict`: 모든 타겟의 계산 결과 및 주문 목록을 포함하는 구조

---

### get_daily_report
현재 모든 RAOEO 타겟의 상태를 조회합니다.

#### Returns
- `dict`:
  - `date`: 날짜
  - `targets`: 각 종목별 상태 정보 (`config`, `holdings`, `orders`, `status`)
  - `orders`: 전체 주문 목록

---

### execute_orders
계산된 모든 주문을 KIS API를 통해 순차적으로 실행합니다.

---

### save_history
실행 결과를 `raoeo_history.json`에 저장합니다. 다중 타겟 구조를 지원합니다.

## History File (히스토리 파일)

`~/KIS_config/raoeo_history.json` 구조:

```json
[
    {
        "date": "2026-02-08",
        "targets": {
            "SOXL": {
                "state": "accumulating",
                "config": { ... },
                "holdings": { ... },
                "orders": [ ... ]
            },
            "FAS": {
                "state": "holding",
                ...
            }
        }
    }
]
```

히스토리는 **최신 순** (index 0이 가장 최근)으로 저장되는 리스트입니다.