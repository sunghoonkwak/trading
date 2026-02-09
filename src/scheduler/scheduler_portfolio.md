# Portfolio Report Scheduler (`scheduler_portfolio.py`)

이 모듈은 매일 오전 7시에 실행되는 포트폴리오 리포트 로직을 담당합니다.

## Public API (`scheduler_portfolio.py`)

### run_daily_portfolio_report
매일 아침 실행되는 메인 잡 함수입니다.
- **Data Collection (화-토)**: 전날 장 마감 데이터를 수집하여 `portfolio_history/`에 JSON 파일로 저장합니다.
- **Notification (화-토)**: 수집된 데이터를 기반으로 요약 리포트를 생성하고 텔레그램으로 전송합니다.
- **Monday**: 새 데이터를 fetch하지 않고, 금요일에 저장된 데이터를 로드하여 리포트를 재전송합니다. (한국 한주 시작 전 재확인용)
- **Sunday**: 일요일은 아무 작업도 수행하지 않습니다.

### get_comparison_stats
현재 포트폴리오 가치와 과거 기록을 비교하여 성과 분석 텍스트를 생성합니다.
- **Format**: 가독성을 위해 `<code>` 태그를 사용하여 우측 정렬하고, KRW 변동량은 `k` 단위로 표시합니다.
  - 예:
    ```html
    <b>📅 1 Day</b>
    <code>
    🇰🇷 🔺  +1,234 k,  +1.20%
    🇺🇸 🔺    +123,  +1.00%
    </code>
    ```
- **KRW & USD**: 원화(KRW)와 달러(USD) 기준의 총 자산 변동을 모두 계산하여 제공합니다.
    - USD 계산 우선순위: `total_value_usd` (저장된 값) > `stats` 필드 합계 > 강제 환산 (KRW/환율)
- **비교 기간**: 1일 전, 1주일 전(5일), 1달 전(20일)
- **Top Movers**: 전일 대비 변동폭이 큰 종목 Top 3를 추출하여 보여줍니다. (동일 종목 복수 계좌 보유 시 통합하여 계산)

### get_total_equity / get_total_equity_usd
총 자산 가치를 계산하는 내부 헬퍼 함수들입니다.
- **Priority**: `merged_data`의 `stats` 필드(stock + cash)를 가장 우선적으로 사용하여 정확도를 높입니다.
- **Fallback**: `stats` 데이터 부재 시, 보유 종목의 현재가와 수량을 기반으로 직접 계산합니다. (환율 적용 주의)

## File Storage
리포트 및 히스토리 파일은 다음 경로에 저장됩니다:
- `~/KIS_config/portfolio_history/portfolio_YYYYMMDD.json`
- `~/KIS_config/portfolio_history/report_YYYYMMDD.txt` (백업용)
