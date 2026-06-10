# KIS WebSocket Notifications (`src/broker/kis_ws_notifications.py`)

WebSocket 재연결 Telegram 알림 기준을 관리합니다.

- 연결이 끊어진 순간에는 Telegram 알림을 보내지 않습니다.
- 재연결 실패가 3회 이상 누적될 때부터 실패 알림을 보냅니다.
- 3회 이상 실패한 뒤 재연결에 성공한 경우에만 복구 알림을 보냅니다.
- 1~2회 실패 후 성공하는 일시적인 끊김은 로그/UI 상태로만 남깁니다.
