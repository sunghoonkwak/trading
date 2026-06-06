# RAOEO Batch Backtest Script (`scripts/backtest/raoeo/batch_backtest.py`)

RAOEO 전략의 성과를 다양한 시작/종료일 조합에 대해 대량으로 시뮬레이션하고 통계적 분석 보고서를 생성하는 배치 백테스트 스크립트입니다.

## Core Logic (핵심 로직)

1.  **날짜 조합 생성**: 2022년부터 2026년까지 월 단위로 시작일과 종료일의 모든 조합(총 408개)을 생성합니다.
2.  **데이터 최적화 로딩**: `yfinance`를 통해 전체 기간 데이터를 한 번에 로드하여 시뮬레이션 속도를 높입니다.
3.  **다중 케이스 시뮬레이션**: 각 기간 조합에 대해 6가지 전략 케이스(단리/복리, 투입중단/물타기/방어매도)를 실행합니다.
4.  **통계 산출 및 이상치 분석**: 각 케이스별로 CAGR 통계(평균, 백분위수 등)를 계산하고, Tukey의 IQR 공식을 사용해 예외적인 시뮬레이션 구간(Outlier)을 추적합니다.
5.  **보고서 출력**: 분석 결과와 이상치 목록을 마크다운 형식의 보고서(`batch_analysis_report.md`)로 저장합니다.
6.  **시각화 (Visualization)**: `seaborn`과 `matplotlib`을 사용하여 성과 분포를 직관적으로 비교할 수 있는 Box Plot 그래프(`batch_cagr_distribution.png`)를 생성합니다.

## Key Functions (주요 함수)

### `calculate_cagr`
수익금과 투자 기간을 바탕으로 연평균 성장률(CAGR)을 계산합니다.

- **입력 (Input)**:
  - `realized_profit` (float): 실현 수익금
  - `initial_seed` (float): 초기 시드 머니
  - `start_date` (datetime): 시작 날짜
  - `end_date` (datetime): 종료 날짜
- **출력 (Output)**: `float` (CAGR 값)

### `main`
시뮬레이션 기간 조합 생성, 데이터 다운로드, 6개 케이스 실행, 통계 산출,
마크다운 보고서 및 box plot 생성을 순서대로 수행합니다.

통계 산출 로직은 `main()` 내부의 지역 함수 `get_stats()`가 담당합니다.

## Configuration (`strategy_config.json`)

`backtest_raoeo.py`와 동일한 설정을 공유하며, `SOXL` 등의 티커 설정을 로드하여 사용합니다.

## Usage Example (사용 예시)

```bash
# 저장소 루트에서 venv 환경으로 실행
venv/bin/python scripts/backtest/raoeo/batch_backtest.py
```
