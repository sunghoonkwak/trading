# Telegram Portfolio (`telegram_portfolio.py`)

이 모듈은 포트폴리오 요약 및 리밸런싱 관련 Telegram 명령어를 처리합니다.

## Commands (명령어)

| Command | Description |
|---------|-------------|
| `/portfolio` | **대화형(Interactive)** 포트폴리오 관리 시작. 종목 버튼을 통해 상세 정보 조회 |
| `/portfolio_weight` | 목표 비중 대비 리밸런싱 제안. F&G 지수 기반 현금 배분 및 그룹 처리 |
| `/placed_orders` | 현재 미체결 주문 목록을 보여줍니다. |

## Functions (함수)

### cmd_portfolio
포트폴리오 대화를 시작합니다. 인라인 버튼 형태로 종목 리스트를 제공합니다.

### format_portfolio_summary
포트폴리오 요약을 포맷팅합니다. 환율과 **F&G 지수**를 헤더에 표시합니다.

### format_weight_diffs
리밸런싱 정보를 포맷팅합니다.
- **F&G 지수**를 헤더에 표시
- 그룹 constituents는 main ticker에 합산되어 표시

### timeout_handler
60초 동안 활동이 없을 경우 세션을 자동으로 종료합니다.

---

## Technical Notes

- **F&G Index**: `utils.get_fear_and_greed()`를 통해 10분 캐싱된 F&G 지수 표시
- **Group Handling**: Constituents의 보유비중은 main ticker에 합산
- **Caching**: `get_portfolio_data()`를 통해 포트폴리오 정보를 가져옵니다.
- **Exception Resilience**: 모든 ConversationHandler 핸들러는 try-except로 감싸져 있어, Telegram API Timeout 시에도 올바른 상태값(`ConversationHandler.END` 또는 `SELECT_TICKER`)을 반환합니다. 이를 통해 대화 상태 꼬임을 방지합니다.
- **Retry on Timeout**: `wrap_reply`/`wrap_edit`는 `TimedOut`/`NetworkError` 발생 시 최대 2회 재시도합니다 (1초 간격).

