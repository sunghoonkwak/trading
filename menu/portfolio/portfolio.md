# portfolio.md

이 모듈은 사용자의 계좌 정보를 로드하고, 계좌별로 포트폴리오를 관리합니다.

## Purpose (목적)

KIS OpenAPI를 통해 관리 가능한 한국투자증권 계좌와, OpenAPI를 지원하지 않는 금융사의 계좌 정보를 통합 관리합니다.
- **한국투자증권**: KIS API를 통해 실시간 데이터 조회
- **기타 금융사**: Google Sheets에 입력된 데이터 조회 및 현재가(GOOGLEFINANCE) 활용

## Workflow (동작 프로세스)

1. **KIS API 데이터 로드**: `fetch_account_data()`를 통해 한국투자증권 계좌의 KR/US 주식 및 예수금 조회
2. **GSheet 데이터 로드**: `_parse_worksheet_data()`를 통해 GSheet 데이터(Ticker, 현재가 포함) 조회
3. **데이터 병합**: 두 소스의 데이터를 통합하여 `portfolio.json`에 저장
4. **포트폴리오 요약**: `portfolio_menu()`를 통해 통합 자산 현황 표시 및 Excel 내보내기 지원

### portfolio data format (portfolio.json)
```json
{
  "metadata": { "last_updated": "2025-12-31T08:17:37Z" },
  "owners": [
    {"id": "owner_01", "name": "곽성훈"},
    {"id": "owner_02", "name": "염인선"}
  ],
  "asset_info": {
    "AVGO": {"name": "Broadcom, Inc.", "market": "US", "asset_type": "Stock", "currency": "USD"}
  },
  "accounts": [
    {"id": "acc_01", "owner_id": "owner_01", "name": "한국투자증권"}
  ],
  "holdings": [
    {
      "account_id": "acc_01",
      "ticker": "AVGO",
      "name": "Broadcom, Inc.",
      "qty": 1.0,
      "avg_price": 352.41,
      "cur_price": 349.85
    }
  ],
  "cash_holdings": [
    {"account_name": "한국투자증권", "amount": 146602.0, "currency": "KRW"},
    {"account_name": "한국투자증권", "amount": 1275.61, "currency": "USD"}
  ]
}
```

## Public API

### get_portfolio
포트폴리오 데이터를 가져와 가중치/목표를 계산합니다.

**Returns**: dict
- `merged_data`: 티커별 병합된 보유 데이터
- `total_value_usd`: 총 자산 가치 (USD)
- `current_weights`: 티커별 현재 비중
- `targets`: 티커별 목표 비중
- `stats`: 요약 통계 (us_stock_usd, kr_cash_krw 등)
- `exchange_rate`: KRW/USD 환율
- `error`: 에러 메시지 (없으면 None)

---

### calc_weight_diffs
현재 비중과 목표 비중의 차이를 계산하고 리밸런싱을 위한 예상 목표 수량을 산출합니다.

**Parameters**:
- `merged_data`: 티커별 병합 데이터
- `current_weights`: 현재 비중 dict
- `targets`: 목표 비중 dict
- `total_value_usd`: 총 자산 가치 (USD)
- `exchange_rate`: KRW/USD 환율

**Returns**: list
- `abs_diff` 기준 내림차순 정렬된 리스트. 각 항목은 `ticker`, `name`, `cur_w`, `tgt_w`, `diff`, `abs_diff`, `qty_diff`(정수 수량) 포함.

---

### portfolio_menu
메인 메뉴 `p` 옵션 선택 시 실행되는 대화형 UI입니다.
- `get_portfolio()`를 호출하여 데이터 획득
- 실시간 환율 및 각 자산의 `cur_price`를 반영하여 요약 테이블 생성
- `1` 키 입력 시 `_check_portfolio_balance` 실행
- `2` 키 입력 시 `_export_portfolio_excel` 실행
- `3` 키 입력 시 `Value Averaging` 실행 (가치 평균화 적립식 투자 계산 및 주문)
- `q` 키 입력 시 메인 메뉴 복귀

---

## Internal Functions (Private)

### _parse_worksheet_data
GSheet 워크시트 데이터를 파싱하여 내부 데이터 구조로 변환합니다.

**Sheet Structure (필수)**
| Column | Description |
|--------|-------------|
| A | Ticker (종목 코드 - 필수) |
| B | 종목명 |
| C | 보유 수량 |
| D | 평균 단가 |
| F | 계좌명 |
| G | 현재가 (GOOGLEFINANCE 함수 권장) |

- **Special Rows**: `예수금` 포함 시 `cash_holdings`로 분류.

---

### _check_portfolio_balance
현재 포트폴리오 비중과 목표 비중(`portfolio_weights.json`)을 비교하여 리밸런싱 필요 내역을 출력 형식으로 표시합니다.
- `calc_weight_diffs()`를 내부적으로 호출하여 계산된 데이터를 획득합니다.
- **Features**:
  - **Color Coding**: 매수 필요(Green/Positive), 매도 필요(Red/Negative) 색상 구분.
  - **Index (#)**: 전체 목록에서의 순위 표시.
  - **Qty**: 목표 비중 달성을 위한 예상 매수/매도 수량(정수) 표시.
  - **Pagination**: 6개 항목씩 페이지 표시 (`Enter`: 다음, `q`: 종료).

---

### _update_portfolio
KIS API와 GSheet 데이터를 병합하여 `portfolio.json`을 갱신합니다.
- **Returns**: `tuple (success: bool, kis_data: dict or None)`
- **Merge Order**: KIS API 데이터 로드 → GSheet 데이터 로드 → `portfolio.json` 저장.

---

### _export_portfolio_excel
통합 포트폴리오를 **Excel (.xlsx)** 파일로 내보냅니다.
- **Library**: `openpyxl` 사용.
- **Styling**: Header 진하게(Bold), 가운데 정렬, 백분율/천 단위 콤마 포맷.
- **Columns**: `Ticker`, `Name`, `Cur Wgt`, `Tgt Wgt`, `Qty`, `Avg Price`, `Cur Price`, `Invest`, `Cur Val`, `Change`, `Ret %`
- **Filename**: `portfolio_export_YYYYMMDD_HHMMSS.xlsx`
