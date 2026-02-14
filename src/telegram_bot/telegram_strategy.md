# Telegram Strategy Module (`src/telegram_bot/telegram_strategy.py`)

텔레그램 봇의 `/strategy` 명령어 처리를 담당하는 모듈입니다.
사용자에게 현재 전략(RAOEO, Value Averaging)의 상태 보고서를 보여주고, 실행(Execute) 승인을 받으면 주문을 실행합니다.

# Core Logic (핵심 로직)

1. **상태 조회**: `execution_service.py`를 호출하여 계산된 보고서를 가져옵니다 (`execute=False`).
2. **보고서 출력**: 주문이 없거나 휴장일인 경우에도 사용자에게 현재 상태(예산, 괴리율 등)를 보여줍니다.
3. **승인 프로세스**: 실행 가능한 주문이 있으면 `InlineKeyboardButton`으로 `Execute` 버튼을 생성합니다.
4. **실행**: 사용자가 승인하면 `execution_service.py`를 호출하여 실제 주문을 실행하고 결과를 업데이트합니다.

# Key Functions (주요 함수)

## `format_strategy_report`
RAOEO와 Value Averaging 보고서를 통합하여 가독성 높은 텍스트로 변환합니다.

- **입력 (Input)**: `raoeo_report` (dict), `va_report` (dict).
- **출력 (Output)**: `str` (텔레그램 메시지 텍스트).

## `cmd_strategy`
`/strategy` 명령어 핸들러입니다.
- **기능**: 보고서 생성 및 버튼 표시.
- **반환**: `ConversationHandler` 상태 (확인 대기 중).

## `handle_strategy_callback`
사용자의 버튼 클릭(실행/취소)을 처리합니다.
- **기능**: 실행 버튼 클릭 시 `execute=True`로 전략 실행.

# Configuration (`telegram.txt`)

```
bot_token,chat_id
```
텔레그램 봇 토큰과 채팅 ID는 `~/KIS_config/telegram.txt` 파일에서 로드됩니다.

# Usage Example (사용 예시)

```python
# 텔레그램에서 명령어 입력
/strategy

# 결과
📊 Strategy Report - 2026-02-14
...
[✅ Execute All] [❌ Cancel]
```
