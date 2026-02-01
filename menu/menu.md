# Trading Menu (`menu/menu.py`)

## 개요
실질적인 트레이딩 작업을 수행하는 메인 메뉴입니다. Super Menu에서 `3`번을 선택하여 진입합니다. Web Event Viewer와 함께 사용하여 실시간 상황을 보면서 명령을 내릴 수 있습니다.

## 메뉴 구성
1. **Account Info**: 현재 잔고 및 보유 종목(Portfolio)을 조회합니다.
2. **Place Order**: 매수/매도 주문을 수동으로 전송합니다. 지정가/시장가 주문이 가능합니다.
3. **Manage Open Orders**: 미체결 주문을 조회하고 정정/취소합니다.
4. **RAOEO Strategy**: RAOEO 자동 매매 전략 메뉴로 진입합니다.
5. **Portfolio**: 포트폴리오 관리 메뉴로 진입합니다.

## 시스템 관리 기능
- **Toggle Log Level (`0`)**: 로그 레벨을 INFO/DEBUG/ERROR로 순환 변경합니다.
- **Clear & Sync (`c`)**: 웹 뷰어의 시세 화면을 정리하고 미체결 주문을 재동기화합니다.
- **Back to Super Menu (`q`)**: 상위 메뉴로 돌아갑니다.

## 변경 사항
- **Event Viewer 연동 제거**: 과거 `v` 키로 터미널 기반 Event Viewer를 실행했으나, 이제는 웹 브라우저(`http://<ip>:8080`)를 사용하므로 해당 옵션이 제거되었습니다.
