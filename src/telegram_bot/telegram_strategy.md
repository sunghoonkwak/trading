# Telegram Strategy Handler (`src/telegram_bot/telegram_strategy.py`)

`/strategy` 명령어를 처리하여 RAOEO 및 Value Averaging 전략의 현황을 확인하거나 수동으로 실행하는 핸들러입니다.

## Core Logic (핵심 로직)

1. **Strategy Status Check (전략 상태 확인)**:
   - `execution_service.run_raoeo_strategy`와 `run_va_strategy`를 호출하여 현재 시장 상황과 주문 생성 여부를 확인합니다.
   - 이때 `execute=False`로 호출하여 실제 주문은 전송하지 않고 시뮬레이션 결과만 받습니다.

2. **Interactive Execution (대화형 실행)**:
   - 생성된 리포트를 사용자에게 보여주고, 실행 가능한 주문이 있으면 사용자가 실행 또는 취소를 선택합니다.
   - RAOEO 매수 대금이 KIS 해외주문가능 USD를 초과하면 `cash_ticker` 매도 후 실행, 조달 없이 실행, 취소의 세 가지 버튼을 제공합니다.
   - 해외주문가능 USD가 충분하면 조달 없이 실행과 취소의 두 가지 버튼만 제공합니다.
   - 실행 버튼을 고르기 전에 총 RAOEO 매수 필요액, KIS 해외주문가능 USD,
     그리고 조달 매도 선택 시 접수될 `cash_ticker` 매도 수량/가격/예상금액을
     리포트에 표시합니다.
   - 조달 매도는 버튼 승인 시 현재 정보로 새로 계산하며, 접수 실패 또는 조달 불가이면 RAOEO와 Value Averaging을 모두 실행하지 않습니다.

## Key Functions (주요 함수)

### `cmd_strategy`
`/strategy` 명령어 입력 시 호출되는 메인 함수입니다.
- 두 전략(RAOEO, VA)을 차례로 실행하고 통합 리포트를 생성하여 전송합니다.

### `handle_strategy_callback`
사용자가 실행 방법 버튼을 눌렀을 때 호출되는 콜백 함수입니다.
- `pending_orders`가 있는 경우에만 실행을 시도하며, 결과를 다시 사용자에게 리포팅합니다.
- `cash_ticker` 매도 후 실행을 고르면 매도 접수 성공 후 5초를 기다린 뒤 전략을 실행하며, 조달 결과는 RAOEO 이력에 별도로 저장됩니다.
- 실행 후에는 히스토리가 업데이트되므로 중복 실행되지 않습니다.

## Configuration (None)
별도의 설정 파일이 없습니다.

## Usage Example (사용 예시)

**Telegram 채팅방**:
```
/strategy
```
**Bot 응답**:
```
📊 Strategy Report
... (리포트 내용) ...
[Sell cash_ticker & Execute] [Execute Without Cash Sale] [Cancel]
```
