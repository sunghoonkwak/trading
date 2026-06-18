# Calculate Weights (`src/data/calculate_weights.py`)

이 모듈은 `~/KIS_config/portfolio_weights.json`의 `core` /
`satellites` 구조를 사용해 포트폴리오 목표 비중을 계산합니다.

## 목적

1. Fear & Greed 지수에 따라 현금 목표 비중을 결정합니다.
2. Extreme Fear 구간에서는 기존 SOXL/TQQQ 고정 레버리지 비중을 추가합니다.
3. `core` 항목의 `score` 합계를 기준 점수로 사용합니다.
4. `satellites` 항목은 `ratio * core_score`로 점수화합니다.
5. `group` 항목은 목표를 대표 티커에 만들고, 구성 티커의 현재 보유 비중을
   대표 티커에 합산합니다.
6. `name`이 `Bonds`인 group은 현금성 보유분으로 간주해 목표 비중을
   만들지 않습니다.
7. `strategy: weighted_split` 항목은 목표 비중을 내부 구성 종목의
   `weight` 비율대로 나눕니다.

## 설정 구조

```json
{
  "cash_strategy": {
    "min": 0.10,
    "mid": 0.20,
    "max": 0.30
  },
  "core": [
    {
      "type": "group",
      "name": "Nasdaq100",
      "score": 120,
      "main_ticker": "QQQM",
      "constituents": ["QQQ", "QLD", "379810"]
    }
  ],
  "satellites": [
    {
      "type": "group",
      "name": "Bonds",
      "ratio": 0,
      "main_ticker": "TLTW",
      "constituents": ["TLT", "453850"]
    },
    {
      "type": "individual",
      "ticker": "TSM",
      "ratio": 0.10
    },
    {
      "type": "strategy",
      "name": "KR_DIV",
      "strategy": "weighted_split",
      "ratio": 0.20,
      "constituents": [
        { "ticker": "005385", "weight": 2 },
        { "ticker": "086790", "weight": 3 }
      ]
    }
  ]
}
```

이 모듈은 새 `core` / `satellites` 구조만 지원합니다. 기존
`groups`, `individual_stocks`, `kr_dividend_strategy` 형식은 더 이상
런타임 설정 형식으로 사용하지 않습니다.

## 계산 방식

중립 구간에서 `cash_strategy.mid = 0.20`이면:

```text
stock_total = 1.0 - 0.20 = 0.80
```

`core`가 다음과 같다면:

```text
Nasdaq100 120
S&P500     40
Dividend   20
```

기준 점수는:

```text
core_score = 120 + 40 + 20 = 180
```

`satellites`는 이 `core_score`만 기준으로 점수화합니다.

```text
TLTW ratio 0.10 -> 18점
TSM  ratio 0.10 -> 18점
QCOM ratio 0.15 -> 27점
```

최종 비중은:

```text
item_weight = item_score / total_score * stock_total
```

## 항목 타입

### `individual`

`ticker`에 직접 목표 비중을 생성합니다.

### `group`

`main_ticker`에 목표 비중을 생성합니다. `constituents`는 현재 비중과
평가액을 계산할 때만 사용합니다.

예를 들어 `main_ticker`가 `TLTW`이고 `constituents`가 `["TLT"]`이면:

```text
목표 비중: TLTW
현재 비교 비중: TLTW + TLT
```

`name`이 `Bonds`인 group은 예외입니다. 이 group은 목표 비중을 0으로
고정하고 리밸런싱 매수/매도 목록에서 제외합니다. 현재 보유액은 현금
현재 비중에 더해 표시합니다.

### `strategy` + `weighted_split`

항목 목표 비중을 만든 뒤, `constituents`의 `weight` 비율대로 나눕니다.
`KR_DIV` 같은 내부 종목 묶음을 표현할 때 사용합니다.

## 주요 함수

### `get_cash_weight`

Fear & Greed 지수에 따라 현금 비중을 결정합니다.

### `calculate_target_weights`

설정과 Fear & Greed 지수를 기반으로 목표 비중을 계산합니다.

반환값:

- `target_weights`: 티커별 목표 비중
- `total_score`: core 점수와 satellite 점수를 더한 총점
- `cash_weight`: 목표 현금 비중

### `calculate_current_group_weights`

현재 보유 비중에서 group의 구성 티커를 대표 티커로 합산합니다.

### `calculate_rebalancing`

목표 비중과 현재 비중의 차이를 계산합니다.
