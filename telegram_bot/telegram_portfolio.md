# telegram_portfolio.py

이 모듈은 포트폴리오 요약 및 리밸런싱 관련 Telegram 명령어를 처리합니다.

## Commands (명령어)

| Command | Description |
|---------|-------------|
| `/portfolio_summary` | 현재 포트폴리오 자산 구성 요약 (국가별, 자산군별 비중) |
| `/portfolio_weight` | 목표 비중 대비 현재 비중의 차이와 리밸런싱 제안 (매수/매도 수량) |

## Functions (함수)

### format_portfolio_summary
`get_portfolio()`에서 얻은 데이터를 모바일 가독성에 최적화된 형식으로 변환합니다. 총 자산($/₩), 현금 비중, 국가별 비중 등을 포함합니다.

### format_weight_diffs
`calc_weight_diffs()` 결과를 바탕으로 매수/매도 종목을 구분하여 리스트업합니다. 차이가 0.5% 이상인 종목들만 표시됩니다.

### register_portfolio_handlers
텔레그램 애플리케이션 인스턴스에 포트폴리오 관련 명령어 핸들러를 등록합니다.

### get_portfolio_commands_desc
초기화 메시지에 포함할 포트폴리오 명령어 설명을 반환합니다.

## Technical Notes
- **Thread Safety**: `get_portfolio(silent=True)`를 사용하여 터미널 UI 갱신을 방지하고, `add_alert`를 통해 스레드 안전하게 시스템 알림을 보냅니다.
- **Mobile Optimized**: 좁은 모바일 화면에서도 정보를 한눈에 파악할 수 있도록 이모지와 굵은 텍스트를 활용합니다.
