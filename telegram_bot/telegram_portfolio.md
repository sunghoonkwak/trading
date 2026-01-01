# telegram_portfolio.py

이 모듈은 포트폴리오 요약 및 리밸런싱 관련 Telegram 명령어를 처리합니다.

## Commands (명령어)

| Command | Description |
|---------|-------------|
| `/portfolio` | **대화형(Interactive)** 포트폴리오 관리 시작. 종목 버튼을 통해 상세 정보 조회 |
| `/portfolio_weight` | 목표 비중 대비 현재 비중의 차이와 리밸런싱 제안 (매수/매도 수량) |

## Functions (함수)

### cmd_portfolio
포트폴리오 대화를 시작합니다. 인라인 버튼 형태로 종목 리스트를 제공하며 `ConversationHandler`를 통해 사용자의 다음 선택(버튼 클릭 또는 텍스트 입력)을 대기합니다.

### handle_ticker_callback
사용자가 종목 버튼을 클릭했을 때 실시간 시세를 포함한 상세 정보를 출력합니다.

### timeout_handler
60초 동안 활동이 없을 경우 세션을 자동으로 종료하고 버튼 메시지를 업데이트합니다. `TypeHandler`를 사용하여 텔레그램 엔진이 보내는 `None` 신호를 안정적으로 처리합니다.

### register_portfolio_handlers
텔레그램 애플리케이션 인스턴스에 포트폴리오 관련 `ConversationHandler`를 등록합니다. 입구는 `/portfolio`, 종료 조건은 `/cancel` 또는 60초 타임아웃입니다.

### get_portfolio_commands_desc
초기화 메시지에 포함할 포트폴리오 명령어 설명을 반환합니다.

## Technical Notes
- **Thread Safety**: `get_portfolio(silent=True)`를 사용하여 터미널 UI 갱신을 방지하고, `add_alert`를 통해 스레드 안전하게 시스템 알림을 보냅니다.
- **Price Fetching**: 시세 정보가 부족할 경우 `menu.handle_account_info.fetch_price`를 호출하여 KIS API로부터 최신가를 보충합니다. 이때 거래소 매핑은 자동으로 처리됩니다.
- **Mobile Optimized**: 좁은 모바일 화면에서도 정보를 한눈에 파악할 수 있도록 이모지와 굵은 텍스트를 활용합니다.
