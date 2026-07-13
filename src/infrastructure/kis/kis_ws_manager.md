# KIS WebSocket Manager

`infrastructure.kis.kis_ws_manager`는 KIS WebSocket 연결, 구독, 시작과
종료 timeout을 관리하는 infrastructure adapter다.

`src/main.py`가 시작 전에 다음 runtime collaborator를 주입한다.

- 국내 사용 여부와 국내/해외 관심 종목, 해외 종목 market prefix
- best-effort alert와 WebSocket lifecycle state publisher
- application-owned KIS event handler

Collaborator가 조립되지 않은 상태에서는 초기화가 실패한다. 이 fail-closed
동작은 WebSocket lifecycle, 구독, stop timeout의 기존 동작을 바꾸지 않는다.
