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
4. **포트폴리오 요약**: `show_portfolio_summary()`를 통해 통합 자산 현황 표시 및 CSV 내보내기 지원

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

## Function (기능)

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

- **Account Mapping**: 계좌명에 `인선` 포함 시 `owner_02`, 그 외 `owner_01` 할당.
- **Special Rows**: `예수금` 포함 시 `cash_holdings`로 분류.

---

### update_portfolio
KIS API와 GSheet 데이터를 병합하여 `portfolio.json`을 갱신합니다.
- **Merge Order**: KIS API 데이터 로드 → GSheet 데이터 로드 → `portfolio.json` 저장.
- **Name Sync**: Ticker를 기준으로 `asset_info`와 `holdings`의 종목명을 동기화합니다.

---

### export_portfolio_csv
통합 포트폴리오를 CSV 파일로 내보냅니다.
- **Merge Tickers**: 여러 계좌에 분산된 동일 종목을 하나의 행으로 병합합니다 (단가는 가중평균 적용).
- **Sorting Order**:
  1. **US Stocks** (알파벳 순)
  2. **USD Cash**
  3. **KR Stocks** (코드 순)
  4. **KRW Cash**
- **Columns**: `ticker`, `item_name`, `qty`, `avg_price`, `current_price`, `investment`, `current_value`, `change`, `return_pct`
- **Filename**: `portfolio_export_YYYYMMDD_HHMMSS.csv`

---

### show_portfolio_summary
메인 메뉴 `p` 옵션 선택 시 실행되는 대화형 UI입니다.
- 실시간 환율 및 각 자산의 `cur_price`를 반영하여 요약 테이블 생성.
- `1` 키 입력 시 `export_portfolio_csv` 실행.
- `q` 키 입력 시 메인 메뉴 복귀.

#### Output
- 포트폴리오 현황 요약 화면 출력 및 CSV 생성 지원.

