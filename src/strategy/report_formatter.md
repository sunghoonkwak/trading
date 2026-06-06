# Report Formatter (`src/strategy/report_formatter.py`)

이 모듈은 전략 실행 결과를 Telegram 봇이 전송할 수 있는 포맷(HTML)으로 변환합니다. `StrategyStatus`에 따라 적절한 아이콘과 메시지를 생성합니다.

## Core Logic (핵심 로직)

1. **Structured Formatting (구조화된 포맷팅)**:
   - 각 전략 리포트(`Dict`)를 받아 `Status`, `Market Status`, `Orders`, `Execution Results` 섹션으로 나누어 출력합니다.
   - RAOEO 수동 실행 리포트에 `cash_funding` 컨텍스트가 있으면 매수 필요액, 주문가능 USD, 조달 매도 예정 주문을 함께 표시합니다.

2. **Status Mapping (상태 매핑)**:
   - `StrategyStatus` Enum 값(`EXECUTED`, `PARTIAL`, `ALREADY_DONE` 등)을 사용자 친화적인 메시지와 이모지로 변환합니다.

## Key Functions (주요 함수)

### `format_strategy_report`
RAOEO와 Value Averaging 전략의 통합 리포트를 생성합니다.

- **입력 (Input)**:
  - `raoeo_report` (Dict): RAOEO 실행 결과
  - `va_report` (Dict): VA 실행 결과
- **출력 (Output)**: `str` (HTML 포맷 문자열)

### `format_rebalancing_report`
리밸런싱 전략의 리포트를 생성합니다.

- **입력 (Input)**:
  - `reb_report` (Dict): 리밸런싱 실행 결과
- **출력 (Output)**: `str` (HTML 포맷 문자열)

## Usage Example (사용 예시)

```python
from strategy.report_formatter import format_strategy_report

report_html = format_strategy_report(raoeo_result, va_result)
# Telegram 전송
await update.message.reply_text(report_html, parse_mode='HTML')
```
