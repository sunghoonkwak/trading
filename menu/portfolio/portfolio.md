# Portfolio (`portfolio.py`)

이 모듈은 사용자의 계좌 정보를 로드하고, 계좌별로 포트폴리오를 관리합니다.

## Purpose (목적)

KIS OpenAPI를 통해 관리 가능한 한국투자증권 계좌와, OpenAPI를 지원하지 않는 금융사의 계좌 정보를 통합 관리합니다.
- **한국투자증권**: KIS API를 통해 실시간 데이터 조회
- **기타 금융사**: Google Sheets에 입력된 데이터 조회 및 현재가(GOOGLEFINANCE) 활용

## Workflow (동작 프로세스)

1. **Integrated Data Fetching**: `data.data_service.get_portfolio_data()`를 호출하여 데이터를 로드합니다. (상세 로직: [`data_service.md`](../../data/data_service.md))
   - 내부적으로 KIS API (국내/해외 잔고)와 Google Sheets 데이터를 병합합니다.
2. **Dashboard Rendering**: `portfolio_menu()`가 수신한 통합 데이터를 기반으로 요약 대시보드를 출력합니다.
   - 국가별/자산군별 비중, 총 자산 가치, 환율 정보 등을 시각화합니다.
3. **User Action**:
   - **Check**: `_check_portfolio_balance`로 세부 리밸런싱 필요 내역 조회
   - **Export**: `_export_portfolio_excel`로 엑셀 내보내기
   - **VA**: `value_averaging` 모듈을 통한 적립식 매수 계산

### portfolio data format (portfolio.json)
상세 데이터 구조 및 처리 로직은 [`data/data_service.md`](../../data/data_service.md)를 참조하십시오.

## Public API

### portfolio_menu
메인 메뉴 `p` 옵션 선택 시 실행되는 대화형 UI입니다.
- `data_service.get_portfolio_data()`를 호출하여 데이터 획득
- 실시간 환율 및 각 자산의 `cur_price`를 반영하여 요약 테이블 생성
- `1` 키 입력 시 `_check_portfolio_balance` 실행
- `2` 키 입력 시 `_export_portfolio_excel` 실행
- `3` 키 입력 시 `Value Averaging` 실행 (가치 평균화 적립식 투자 계산 및 주문)
- `q` 키 입력 시 메인 메뉴 복귀

---

## Internal Functions (Private)

### _print_portfolio_summary
포트폴리오 요약 테이블(자산 현황, 현금 비중 등)을 화면에 출력합니다. `portfolio_menu`에서 호출됩니다.

### _check_portfolio_balance
현재 포트폴리오 비중과 목표 비중을 비교하여 리밸런싱 필요 내역을 UI로 표시합니다.
`data_service.get_weight_diffs()`를 사용하여 계산된 비중 차이 정보를 가져옵니다.
이때, **보유하지 않은 종목(수량 0)**도 WebSocket, 국내/해외 시세 API를 자동 조회하여 정확한 매수 수량을 계산합니다.

**Features**:
- **Color Coding**: 매수 필요(Green), 매도 필요(Red) 색상 구분.
- **Pagination**: 6개 항목씩 페이지 표시 (`Enter`: 다음, `q`: 종료).

---

### _export_portfolio_excel
통합 포트폴리오를 **Excel (.xlsx)** 파일로 내보냅니다.
- **Library**: `openpyxl` 사용.
- **Path**: `trading/exports/` 디렉토리에 타임스탬프 파일명으로 저장.

