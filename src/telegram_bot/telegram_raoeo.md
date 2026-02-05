# Telegram RAOEO (`telegram_raoeo.py`)

이 모듈은 RAOEO 무한매수 전략 전용 Telegram 명령어 및 리포팅 기능을 담당합니다.

## Commands (명령어)

| Command | Description |
|---------|-------------|
| `/raoeo` | RAOEO 전략 상태 조회 및 주문 실행 (ConversationHandler) |

## ConversationHandler Flow

```
/raoeo → 상태 표시 → [✅ Yes / ❌ No] 버튼 → 실행 또는 취소
                          ↓
                    60초 타임아웃 시 세션 만료
```

## Functions (함수)

### format_raoeo_report
`build_raoeo_report()` 결과를 Telegram 메시지 형식(**HTML**)으로 변환합니다. 특수 문자 충돌을 방지하면서 가독성 높은 리포트를 생성합니다.

### build_raoeo_keyboard
실행 가능한 주문이 있을 때 ✅ Yes / ❌ No 버튼 키보드를 생성합니다.

### cmd_raoeo
`/raoeo` 명령어의 진입점. RAOEO 상태를 표시하고 주문 확인 버튼을 제공합니다.

### handle_raoeo_callback
Yes/No 버튼 클릭 콜백 처리. Yes 선택 시 `execute_orders()` 호출 후 히스토리에 저장합니다.

### raoeo_timeout_handler
60초 세션 타임아웃 처리. 메시지를 "⏱️ RAOEO session expired."로 업데이트합니다.

### register_raoeo_handlers
텔레그램 애플리케이션 인스턴스에 RAOEO ConversationHandler를 등록합니다.

### get_raoeo_commands_desc
초기화 메시지에 포함할 RAOEO 명령어 설명을 반환합니다.

## Internal State (내부 상태)

- `context.user_data['raoeo_report']`: 현재 세션의 RAOEO 리포트
- `context.user_data['raoeo_msg_id']`: 타임아웃 시 수정할 메시지 ID
- **멀티유저 안전**: 글로벌 캐시 대신 `context.user_data` 사용
- **실패 재시도 지원**: report의 `failed_orders`가 자동으로 `pending_orders`에 포함되어 재시도됩니다.
