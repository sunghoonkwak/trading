# Report Formatter (`src/strategy/report_formatter.py`)

전략 실행 결과를 텔레그램 메시지 포맷(HTML)으로 변환하는 유틸리티 모듈입니다.

# Core Logic (핵심 로직)

1. **RAOEO/VA 섹션**: 종목별 예산, 보유량, 계산된 주문을 통합 리포트로 제공합니다.
2. **Rebalancing 섹션**:
   - 타겟 시드(Target Seed) 및 가용 현금을 표시합니다.
   - 현재 보유량과 함께 주문 후 예상 보유 금액(Est.Total) 및 비중(%)을 보여줍니다.
3. **새로운 상태 처리 (RAOEO)**:
   - `already_executed`: 금일 모든 주문이 이미 성공적으로 완료됨을 표시.
   - `from_history`: 실패한 주문이 포함된 히스토리에서 복원됨을 표시 (재시도 필요).
   - `partial_re_execution`: 실패했던 주문만 선별적으로 재실행했음을 표시.
4. **휴장일 처리**: 주문 가능 여부와 상관없이 계산 결과를 출력하며, 휴장 시 경고 문구를 포함합니다.

# Key Functions (주요 함수)

## `format_strategy_report`
RAOEO 및 VA 결과를 포함한 데일리 통합 전략 보고서를 생성합니다.

## `format_rebalancing_report`
리밸런싱 전용 보고서를 생성합니다. 가용 현금 정보와 자산별 비중 변화를 상세히 보여줍니다.

# Usage Example (사용 예시)

```python
from strategy.report_formatter import format_rebalancing_report
report_text = format_rebalancing_report(reb_result)
```
