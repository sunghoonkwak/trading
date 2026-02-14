# Telegram Rebalancing (`src/telegram_bot/telegram_rebalancing.py`)

텔레그램을 통해 리밸런싱 전략의 상태를 조회하고 수동으로 실행할 수 있는 인터페이스를 제공하는 모듈입니다.

# Core Logic (핵심 로직)

1. **상태 조회**: `/rebalance` 명령어 입력 시 현재 비중 상태와 필요한 리밸런싱 주문을 계산하여 보고합니다.
2. **수동 실행**: 사용자가 텔레그램 버튼을 통해 승인하면 즉시 주문을 집행합니다.
3. **세션 관리**: 실행/취소 시 관련 데이터를 정리하고 일정 시간 응답이 없으면 세션을 종료합니다.

# Key Functions (주요 함수)

## `cmd_rebalance`
`/rebalance` 명령어에 반응하여 현재 리밸런싱 상태 리포트를 전송합니다.

## `handle_reb_callback`
텔레그램의 'Execute' 또는 'Cancel' 버튼 클릭 이벤트를 처리합니다.

## `register_rebalancing_handlers`
텔레그램 봇 애플리케이션에 리밸런싱 관련 핸들러를 등록합니다.

# Usage Example (사용 예시)

텔레그램 채팅창에서:
- `/rebalance`: 현재 리밸런싱 필요 여부 확인
- 버튼 클릭: 주문 집행 또는 취소
