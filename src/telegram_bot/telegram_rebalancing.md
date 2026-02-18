# Telegram Rebalancing Handler (`src/telegram_bot/telegram_rebalancing.py`)

`/rebalance` 명령어를 처리하여 포트폴리오 리밸런싱 현황을 확인하거나 수동으로 실행하는 핸들러입니다.

# Core Logic (핵심 로직)

1. **Rebalancing Status Check (리밸런싱 상태 확인)**:
   - `execution_service.run_rebalancing_strategy`를 호출하여 리밸런싱 필요성과 주문 생성 여부를 확인합니다.
   - 이때 `execute=False` 모드로 호출하여 시뮬레이션 결과만 받습니다.

2. **Interactive Execution (대화형 실행)**:
   - 생성된 리포트(현재 비중, 목표 비중, 필요 주문)를 보여주고, 실행 가능한 주문이 있으면 "실행(Execute)" 버튼을 제공합니다.
   - 사용자가 버튼을 클릭하면 `execute=True`로 다시 전략을 호출하여 주문을 전송합니다.

# Key Functions (주요 함수)

## `handle_rebalance_command`
`/rebalance` 명령어 입력 시 호출되는 메인 함수입니다.
- 리밸런싱 전략을 실행하고 결과 리포트를 생성하여 전송합니다.

## `execute_rebalance_callback`
사용자가 "Execute Rebalance" 버튼을 눌렀을 때 호출되는 콜백 함수입니다.
- `pending_orders`가 있는 경우 실행을 시도하며, 결과를 다시 사용자에게 리포팅합니다.

# Configuration (None)
별도의 설정 파일이 없습니다.

# Usage Example (사용 예시)

**Telegram 채팅방**:
```
/rebalance
```
**Bot 응답**:
```
📊 Rebalancing Report
... (자산 비중 및 주문 내역) ...
[Execute Rebalance] (버튼)
```
