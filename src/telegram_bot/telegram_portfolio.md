# Telegram Portfolio (`telegram_portfolio.py`)

이 모듈은 포트폴리오 요약 및 리밸런싱 관련 Telegram 명령어를 처리합니다.

## Commands (명령어)

| Command | Description |
|---------|-------------|
| `/portfolio` | **대화형(Interactive)** 포트폴리오 관리 시작. 종목 버튼을 통해 상세 정보 조회 |
| `/portfolio_weight` | 목표 비중 대비 리밸런싱 제안. **보유하지 않은 종목(수량 0)도** 실시간 시세/API 조회를 통해 매수 수량을 계산하여 제안합니다. |
| `/placed_orders` | 현재 미체결 주문 목록을 보여줍니다. |

## Functions (함수)

### cmd_portfolio
포트폴리오 대화를 시작합니다. 인라인 버튼 형태로 종목 리스트를 제공하며 `ConversationHandler`를 통해 사용자의 다음 선택(버튼 클릭 또는 텍스트 입력)을 대기합니다.

### handle_ticker_callback
사용자가 종목 버튼을 클릭했을 때 실시간 시세를 포함한 상세 정보를 출력합니다.

### timeout_handler
60초 동안 활동이 없을 경우 세션을 자동으로 종료하고 버튼 메시지를 업데이트합니다. `TypeHandler`를 사용하여 텔레그램 엔진이 보내는 `None` 신호를 안정적으로 처리합니다.

---

### register_portfolio_handlers
텔레그램 애플리케이션 인스턴스에 포트폴리오 관련 `ConversationHandler`를 등록합니다.
- `/portfolio`: 60초 타임아웃

### get_portfolio_commands_desc
초기화 메시지에 포함할 포트폴리오 명령어 설명을 반환합니다.

## Technical Notes

- **Caching**: `get_portfolio_data()`를 통해 포트폴리오 정보를 가져옵니다.
- **Price Fetching**: 비중 계산 시 현재가가 없는 종목(수량 0)은 1) WebSocket, 2) KIS API (`fetch_price`) 순서로 시세를 조회하여 정확한 매수 수량을 계산합니다.
- **Mobile Optimized**: 좁은 모바일 화면에서도 정보를 한눈에 파악할 수 있도록 이모지와 굵은 텍스트를 활용합니다.
