# Telegram Portfolio (`telegram_portfolio.py`)

이 모듈은 포트폴리오 요약 및 리밸런싱 관련 Telegram 명령어를 처리합니다.

## Commands (명령어)

| Command | Description |
|---------|-------------|
| `/portfolio` | **대화형(Interactive)** 포트폴리오 관리 시작. 종목 버튼을 통해 상세 정보 조회 |
| `/portfolio_weight` | 목표 비중 대비 리밸런싱 제안. **보유하지 않은 종목(수량 0)도** 실시간 시세/API 조회를 통해 매수 수량을 계산하여 제안합니다. |
| `/portfolio_va` | **Value Averaging** 주문 계산 및 실행 (순차 처리 방식, 60초 타임아웃) |

## Functions (함수)

### get_portfolio_cached
`get_portfolio()`를 캐싱하여 5분 내 중복 호출 시 캐시된 데이터를 반환합니다.

```python
data = get_portfolio_cached(force_refresh=False)
```

---

### cmd_portfolio
포트폴리오 대화를 시작합니다. 인라인 버튼 형태로 종목 리스트를 제공하며 `ConversationHandler`를 통해 사용자의 다음 선택(버튼 클릭 또는 텍스트 입력)을 대기합니다.

### handle_ticker_callback
사용자가 종목 버튼을 클릭했을 때 실시간 시세를 포함한 상세 정보를 출력합니다.

### timeout_handler
60초 동안 활동이 없을 경우 세션을 자동으로 종료하고 버튼 메시지를 업데이트합니다. `TypeHandler`를 사용하여 텔레그램 엔진이 보내는 `None` 신호를 안정적으로 처리합니다.

---

### cmd_portfolio_va
**Value Averaging** 주문을 종목별로 순차적으로 처리합니다.
1. `get_daily_report`를 호출하여 전체 전략을 계산합니다.
2. 이미 실행된(`executed: true`) 종목은 요약 리스트에 표시합니다.
   - 상세 주문 내역(수량, 가격, Target)을 함께 표시합니다.
3. 실행되지 않은 종목이 있다면 첫 번째 종목부터 순차적으로 사용자에게 물어봅니다.
   - 단, **스케줄러에 의해 Skip된 종목**도 사용자가 수동으로 매수할 기회를 제공하기 위해 대기(Pending) 목록에 포함됩니다.
   - 이미 완전히 실행된(Already Executed) 종목은 상단 요약에 표시됩니다.

### handle_va_callback
Value Averaging 진행 중 사용자의 버튼 입력을 처리합니다:
- **[Yes]**: 표시된 수량만큼 주문 실행 → 결과(성공/실패) 저장 → 다음 종목으로 이동
- **[No/Skip]**: 주문하지 않고 건너뜀 (Skip 기록 저장) → 다음 종목으로 이동하게 됩니다. 스킵된 항목도 기회비용 추적을 위해 타겟 금액과 현재가를 기록합니다.

모든 종목 처리가 끝나면 **최종 요약(Summary)**를 표시합니다:
> ✅ QLD: Order Placed (Target: $150.00)
>    └ Buy 2 shares ($76.94)
> ⏸️ TQQQ (Day 25 | Target $2,109 | Cur $1,943 | -7.8%)
>    └ Hold (Diff inside ±15%)

### va_timeout_handler
60초 타임아웃 시 세션을 종료하고 메시지를 정리합니다.

---

### format_va_single_ticker
단일 종목의 Value Averaging 계산 결과를 Telegram HTML 형식으로 포맷팅합니다. 사용자가 결정을 내리기 쉽도록 필요한 정보(현재가, 목표액, 주문 수량 등)를 강조합니다.

---

### register_portfolio_handlers
텔레그램 애플리케이션 인스턴스에 포트폴리오 관련 `ConversationHandler`를 등록합니다.
- `/portfolio`: 60초 타임아웃
- `/portfolio_va`: 60초 타임아웃

### get_portfolio_commands_desc
초기화 메시지에 포함할 포트폴리오 명령어 설명을 반환합니다.

## Technical Notes

- **Caching**: `get_portfolio_cached()`를 사용하여 5분 내 중복 API 호출을 방지합니다.
- **Price Fetching**: 비중 계산 시 현재가가 없는 종목(수량 0)은 1) WebSocket, 2) KIS API (`fetch_price` or `inquire_price`) 순서로 시세를 조회하여 정확한 매수 수량을 계산합니다.
- **Mobile Optimized**: 좁은 모바일 화면에서도 정보를 한눈에 파악할 수 있도록 이모지와 굵은 텍스트를 활용합니다.
