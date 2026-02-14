# Report Formatter (`src/strategy/report_formatter.py`)

전략 실행 결과(RAOEO, Value Averaging)를 텔레그램 메시지 포맷(HTML)으로 변환하는 유틸리티 모듈입니다.
데이터 구조를 읽기 쉬운 텍스트 리포트로 가공합니다.

# Core Logic (핵심 로직)

1. **RAOEO 섹션**: 각 종목의 예산, 보유량, 계산된 주문을 출력합니다.
2. **Value Averaging 섹션**: 현재 회차(Day), 목표액, 괴리율, 계산된 주문을 출력합니다.
3. **휴장일 처리**: 주문이 있더라도 휴장일 상태이면 경고 문구를 추가합니다.
4. **실행 결과**: 실제 주문이 실행된 경우 성공/실패 여부를 요약하여 하단에 표시합니다.

# Key Functions (주요 함수)

## `format_strategy_report`
통합 전략 보고서 문자열을 생성합니다.

- **입력 (Input)**:
  - `raoeo_report` (dict): RAOEO 실행 결과
  - `va_report` (dict): VA 실행 결과
- **출력 (Output)**: `str` (HTML 포맷팅된 메시지)

# Configuration (None)
별도의 설정 파일이 없습니다.

# Usage Example (사용 예시)

```python
from strategy.report_formatter import format_strategy_report

report_text = format_strategy_report(raoeo_result, va_result)
# 텔레그램 전송
await context.bot.send_message(chat_id, text=report_text, parse_mode='HTML')
```
