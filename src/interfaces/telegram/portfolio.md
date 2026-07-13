# Telegram Portfolio (`src/interfaces/telegram/portfolio.py`)

이 모듈은 포트폴리오 요약 및 리밸런싱 관련 Telegram 명령어를 처리합니다.
`main.py`가 `PortfolioCommandDependencies`를 주입해 등록하며,
`PortfolioCommandHandler` 인스턴스가 해당 factory-owned collaborators를
보유합니다.

## Commands (명령어)

| Command | Description |
|---------|-------------|
| `/portfolio` | **대화형(Interactive)** 포트폴리오 관리 시작. 종목 버튼을 통해 상세 정보 조회 |
| `/gsheet` | Google Sheets 원천 데이터를 다시 읽어 메모리 캐시를 갱신 |
| `/portfolio_weight` | 전체 포트폴리오 기준 목표 비중 대비 리밸런싱 제안. F&G 지수 기반 현금 배분 및 그룹 처리 |
| `/placed_orders` | 현재 미체결 주문 목록을 종목별로 묶어 보여줍니다. |

## Key Functions (주요 함수)

### `cmd_portfolio`
포트폴리오 대화를 시작합니다. 인라인 버튼 형태로 종목 리스트를 제공합니다.

### `format_portfolio_summary`
포트폴리오 요약을 포맷팅합니다. 환율과 **F&G 지수**를 헤더에 표시합니다.

### `format_weight_diffs`
리밸런싱 정보를 포맷팅합니다.
- **F&G 지수**를 헤더에 표시
- 일반 그룹 constituents는 main ticker에 합산되어 그룹명, 대표 티커,
  현재/목표 평가액과 함께 표시
- `name`이 `Bonds`인 그룹은 현금성 보유분으로 간주해 현금 현재 비중에
  합산하고 매수/매도 목록에서는 제외

### `format_placed_orders`
KIS US/KR 및 Toss 미체결 주문을 티커별로 묶고, 각 티커 안에서
매도/매수 섹션으로 나눠 표시합니다.

### `cmd_gsheet`
GSheet source 캐시만 갱신하고 성공/경고 요약을 응답합니다. 포트폴리오
요약 계산이나 broker 조회는 수행하지 않습니다.

### `timeout_handler`
60초 동안 활동이 없을 경우 세션을 자동으로 종료합니다.

---

## Technical Notes

- **F&G Index**: composition root가 주입한 10분 캐싱 F&G adapter로 지수 표시
- **Group Handling**: Constituents의 보유비중은 main ticker에 합산
- **GSheet Caching**: 포트폴리오 결과는 매번 새로 계산하고, 느린 GSheet
  source만 `infrastructure.portfolio.integration`에서 메모리 캐시합니다.
- **Dependency Ownership**: 차단형 의존성 호출을 포함한 모든 명령은 handler
  인스턴스가 보유한 collaborators를 직접 사용하므로, 별도 Telegram factory
  composition끼리 의존성을 공유하지 않습니다. 종목 버튼 설정도 composition
  root가 주입한 loader를 사용하므로 interface가 infrastructure를 import하지
  않습니다.
- **Exception Resilience**: 주요 명령 핸들러는 오류 발생 시 사용자에게 메시지를 보내고 `ConversationHandler.END` 또는 기존 상태를 반환해 대화 상태 꼬임을 줄입니다.
- **Retry on Timeout**: `wrap_reply`/`wrap_edit`는 `TimedOut`/`NetworkError` 발생 시 최대 2회 재시도합니다 (1초 간격).
