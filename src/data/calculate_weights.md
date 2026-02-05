# Calculate Weights (`data/calculate_weights.py`)

이 모듈은 `data/portfolio_weights.json`에 정의된 설정에 따라 포트폴리오의 **목표 비중(Target Weights)**을 동적으로 계산합니다.

## Purpose (목적)

정적인 목표 비중 설정의 한계를 극복하고, 다음과 같은 동적 로직을 처리합니다:
1. **Group Logic**: 그룹(예: Nasdaq) 내에서 기존 보유 종목(Constituents)의 비중을 인정한 후, 나머지 비중을 메인 종목(Main Ticker)에 할당합니다.
2. **US Index Ref**: 개별 종목의 목표 비중을 'US Total Index Score' 대비 비율로 산정합니다.
3. **VIX Strategy**: VIX 지수에 따라 VIX 관련 상품(VIXY 등)의 비중을 동적으로 조절합니다.
4. **Dividend Strategy**: '국내 배당주' 그룹의 비중을 세부 구성 종목들의 내부 비율에 따라 자동 분배합니다.

## Configuration (data/portfolio_weights.json)

계산의 기준이 되는 설정 파일입니다.

```json
{
  "groups": [
    {
      "name": "Nasdaq",
      "target_score": 100,
      "main_ticker": "QQQM",
      "constituents": ["QQQ", "TQQQ", "379810"]
    }
  ],
  "individual_stocks": [
    { "ticker": "AAPL", "ratio": 0.05 }
  ],
  "vix_strategy": {
    "ticker": "VIXY",
    "limit": 15,
    "max": 40,
    "scale": 15
  },
  "kr_dividend_strategy": {
    "source_ticker": "국내 배당주",
    "constituents": [
      { "ticker": "105560", "weight": 20 },
      { "ticker": "086790", "weight": 20 }
    ]
  }
}
```

## Functions (기능)

### calculate_target_weights
현재 보유 비중과 설정을 기반으로 최종 목표 비중을 계산합니다.

#### Logic Step
1. **Base Score 계산**: 그룹 목표 점수 합계를 기준으로 `us_index_weight` 산출.
2. **VIX Score 계산**: 현재 VIX 지수(기본값 14.83)에 따라 점수 동적 계산.
3. **Total Score 산출**: (그룹 점수 + 개별 종목 점수 + 고정 점수 + VIX 점수) 합계.
4. **Weight 분배**:
    - **개별/고정 종목**: (내 점수 / Total Score) 비율 할당.
    - **그룹 (Group Logic)**:
        - 그룹 내 **Constituents**: 현재 보유 비중(`current_weights`) 유지.
        - **Main Ticker**: (그룹 목표% - Constituents 현재 비중 합) 할당. "나머지 채우기" 방식.
    - **배당주 (Dividend Logic)**: `source_ticker`의 비중을 `constituents` 내부 가중치에 따라 쪼개서 할당.

#### Args
- `current_weights` (dict): 현재 포트폴리오의 실제 비중 (그룹 로직 계산용).
- `config` (dict): 로드된 설정 데이터.
- `current_vix` (float, optional): 현재 공포지수.

#### Returns
- `target_weights` (dict): `{ "QQQM": 0.15, "AAPL": 0.03, ... }`
- `total_score` (float): 계산된 총점.

### other utils
- `load_config(path)`: JSON 설정 로드.
- `get_display_width(s)`: 한글 등 전각 문자를 고려한 문자열 폭 계산 (터미널 정렬용).
- `pad_string(s, width)`: `get_display_width`를 이용한 정교한 공백 패딩.
