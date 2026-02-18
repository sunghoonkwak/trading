# Telegram Strategy Handler (`src/telegram_bot/telegram_strategy.py`)

`/strategy` 명령어를 처리하여 RAOEO 및 Value Averaging 전략의 현황을 확인하거나 수동으로 실행하는 핸들러입니다.

# Core Logic (핵심 로직)

1. **Strategy Status Check (전략 상태 확인)**:
   - `execution_service.run_raoeo_strategy`와 `run_va_strategy`를 호출하여 현재 시장 상황과 주문 생성 여부를 확인합니다.
   - 이때 `execute=False`로 호출하여 실제 주문은 전송하지 않고 시뮬레이션 결과만 받습니다.

2. **Interactive Execution (대화형 실행)**:
   - 생성된 리포트를 사용자에게 보여주고, 실행 가능한 주문이 있다면 "실행(Execute)" 버튼을 제공합니다.
   - 사용자가 버튼을 클릭하면 `execute=True`로 다시 전략을 호출하여 주문을 전송합니다.

# Key Functions (주요 함수)

## `handle_strategy_command`
`/strategy` 명령어 입력 시 호출되는 메인 함수입니다.
- 두 전략(RAOEO, VA)을 차례로 실행하고 통합 리포트를 생성하여 전송합니다.

## `execute_strategy_callback`
사용자가 "Execute All" 버튼을 눌렀을 때 호출되는 콜백 함수입니다.
- `pending_orders`가 있는 경우에만 실행을 시도하며, 결과를 다시 사용자에게 리포팅합니다.
- 실행 후에는 히스토리가 업데이트되므로 중복 실행되지 않습니다.

# Configuration (None)
별도의 설정 파일이 없습니다.

# Usage Example (사용 예시)

**Telegram 채팅방**:
```
/strategy
```
**Bot 응답**:
```
📊 Strategy Report
... (리포트 내용) ...
[Execute All] (버튼)
```
