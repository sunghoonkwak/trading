# Calculate Weights (`src/data/calculate_weights.py`)

이 모듈은 `~/KIS_config/portfolio_weights.json`에 정의된 설정에 따라 포트폴리오의 **목표 비중(Target Weights)**을 동적으로 계산합니다.

## Purpose (목적)

F&G(Fear & Greed) 지수 기반 자산 배분 로직 구현:
1. **Cash Allocation**: F&G 지수 구간에 따라 현금 비중 확정.
2. **Leverage Allocation**: Extreme Fear 구간에서 SOXL/TQQQ 고정 비중 할당.
3. **Relative Score**: 주식 총량 내에서 각 종목의 점수 비율에 따라 비중 분배.
4. **Group Logic**: 그룹 내 Constituents 보유비중은 Main Ticker에 합산하여 비교.
5. **Dividend Strategy**: '국내 배당주' 그룹의 비중을 세부 구성 종목들의 내부 비율에 따라 자동 분배.

## Configuration (~/KIS_config/portfolio_weights.json)

```json
{
  "cash_strategy": {
    "min": 0.1,    // F&G <= 20 (Extreme Fear) - aggressive + leverage
    "mid": 0.2,    // 20 < F&G <= 80 (Neutral)
    "max": 0.3     // F&G > 80 (Extreme Greed) - defensive
  },
  // Extreme Fear: cash 10% + SOXL 5% + TQQQ 5% = 80% stocks
  "groups": [
    {
      "name": "Nasdaq100",
      "target_score": 85,
      "main_ticker": "QQQM",
      "constituents": ["QQQ", "379810"]
    }
  ],
  "individual_stocks": [
    { "ticker": "SOXL", "ratio": 0.03 }
  ],
  "kr_dividend_strategy": {
    "source_ticker": "KR_DIV",
    "constituents": [
      { "ticker": "105560", "weight": 3 },
      { "ticker": "086790", "weight": 3 }
    ]
  }
}
```

## Key Functions (주요 함수)

### `get_cash_weight`
F&G 지수에 따라 현금 비중 결정.

### `calculate_target_weights`
현재 보유 비중과 설정을 기반으로 최종 목표 비중을 계산합니다.

#### Logic Step
1. **Cash Weight**: F&G 지수 구간에 따라 현금 비중 확정.
2. **Leverage Allocation**: Extreme Fear 시 SOXL 5% + TQQQ 5% 고정 할당.
3. **Stock Total**: `1.0 - cash_weight - leverage_total`를 주식 총량으로 설정.
4. **Score 계산**: 그룹 점수 합 + 개별 종목 점수 합.
5. **Weight 분배**:
   - **개별 종목**: `(score / total_score) * stock_total`
   - **그룹**: Main Ticker에 전체 그룹 비중 할당.
   - **배당주**: `source_ticker` 비중을 `constituents`에 내부 가중치로 분배.
   - **레버리지**: Extreme Fear 시 고정 비중 추가.

#### Args
- `current_weights` (dict): 현재 포트폴리오의 실제 비중.
- `config` (dict): 로드된 설정 데이터.
- `fear_greed_index` (float): 현재 F&G 지수 (기본값: 50).

#### Returns
- `target_weights` (dict): 목표 비중
- `total_score` (float): 총점
- `cash_weight` (float): 현금 비중

### `calculate_current_group_weights`
그룹 내 Constituents 보유비중을 Main Ticker에 합산.

### `calculate_rebalancing`
목표 비중과 현재 비중의 차이 계산.
