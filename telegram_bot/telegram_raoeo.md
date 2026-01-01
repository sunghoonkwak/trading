# telegram_raoeo

이 모듈은 RAOEO 무한매수 전략 전용 Telegram 명령어 및 리포팅 기능을 담당합니다.

## Commands (명령어)

| Command | Description |
|---------|-------------|
| `/raoeo_report` | 현재 RAOEO 전략 상태 조회 및 주문 계산 (결과 캐싱) |
| `/raoeo_order` | 캐시된 RAOEO 주문 실행 및 히스토리 저장 |

## Functions (함수)

### format_raoeo_report
`build_raoeo_report()` 결과를 Telegram 메시지 형식(Markdown)으로 변환합니다.

### register_raoeo_handlers
텔레그램 애플리케이션 인스턴스에 RAOEO 관련 명령어 핸들러(`/raoeo_report`, `/raoeo_order`)를 등록합니다.

### get_raoeo_commands_desc
초기화 메시지에 포함할 RAOEO 명령어들에 대한 설명을 반환합니다.

## Internal State (내부 상태)
- `_cached_result`: 최근 `/raoeo_report` 실행 시 계산된 주문 데이터를 보관하며, `/raoeo_order` 명령 시 이 데이터를 사용해 실제 주문을 진행합니다.
