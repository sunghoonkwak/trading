# Portfolio Report Scheduler (`scheduler_portfolio.py`)

이 모듈은 매일 오전 7시에 실행되는 포트폴리오 리포트 로직을 담당합니다.

## Public API (`scheduler_portfolio.py`)

### run_daily_portfolio_report
매일 아침 실행되는 메인 잡 함수입니다.
- **Data Collection (화-토)**: 전날 장 마감 데이터를 수집하여 `portfolio_history/`에 JSON 파일로 저장합니다.
- **Notification (월-토)**: 수집된 데이터 혹은 최신 데이터를 기반으로 요약 리포트를 생성하고 텔레그램으로 전송합니다.
- **Sunday**: 일요일은 아무 작업도 수행하지 않습니다.

### get_comparison_stats
현재 포트폴리오 가치와 과거 기록을 비교하여 성과 분석 텍스트를 생성합니다.
- **비교 기간**: 1일 전, 1주일 전(5일), 1달 전(20일)
- **Top Movers**: 전일 대비 변동폭이 큰 종목 Top 3를 추출하여 보여줍니다. (동일 종목 복수 계좌 보유 시 통합하여 계산)

## File Storage
리포트 및 히스토리 파일은 다음 경로에 저장됩니다:
- `~/KIS_config/portfolio_history/portfolio_YYYYMMDD.json`
- `~/KIS_config/portfolio_history/report_YYYYMMDD.txt` (백업용)
