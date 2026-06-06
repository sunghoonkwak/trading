# Telegram Utils (`src/telegram_bot/telegram_utils.py`)

이 모듈은 Telegram 봇에서 공통으로 사용되는 메시징 래퍼 함수들을 제공합니다.
순환 참조 방지를 위해 `telegram_bot.py`에서 분리되었습니다.

## Key Functions (주요 함수)

### `wrap_reply`
`update.message.reply_text`를 래핑하여 메시지 전송과 동시에 UI 알림을 추가합니다.

```python
await wrap_reply(update, "메시지 내용", parse_mode='HTML')
```

---

### `wrap_edit`
`update.callback_query.edit_message_text`를 래핑합니다. InlineKeyboard 상호작용에 사용됩니다.

```python
await wrap_edit(update, "수정된 메시지", parse_mode='HTML')
```

---

### `wrap_send`
`bot.send_message`를 래핑하여 사용자 상호작용 없이 직접 메시지를 전송합니다.
전역으로 설정된 `_bot`과 `_chat_id`를 사용합니다.

```python
await wrap_send("알림 메시지", parse_mode='HTML')
```

---

### `wrap_edit_message`
`bot.edit_message_text`를 래핑합니다. 메시지 ID를 직접 지정하여 기존 메시지를 수정합니다.
타임아웃 핸들러 등에서 `update` 객체 없이 메시지를 수정할 때 사용합니다.

```python
await wrap_edit_message(chat_id, message_id, "수정 내용", parse_mode='HTML')
```

---

### `set_telegram_bot`
봇 초기화 시 호출되어 `wrap_send`, `wrap_edit_message`에서 사용할 봇 인스턴스와 채팅 ID를 설정합니다. 또한, **메인 이벤트 루프(`_main_loop`)를 캡처**하여 이후 다른 스레드에서 안전하게 메시지를 보낼 수 있도록 합니다.

```python
set_telegram_bot(app.bot, chat_id)
```

---

### `send_notification`
**Thread-safe** 동기 알림 전송 함수입니다. 웹소켓 이벤트 핸들러 등 백그라운드 스레드에서 호출할 수 있습니다.

```python
send_notification("📈 Order Filled: SOXL 5 @ $25.00", parse_mode='HTML')
```

- **Args**: `text` (메시지 내용), `parse_mode` (기본값: 'HTML')
- **Thread Safety**: 호출된 스레드가 메인 루프가 아닌 경우, `asyncio.run_coroutine_threadsafe`를 사용하여 봇의 메인 루프에 전송 작업을 위임합니다. 이를 통해 `httpx` 연결 풀 충돌(`Event loop is closed`)을 방지합니다.

---

## Technical Notes

- 모든 래퍼 함수는 메시지의 첫 줄(최대 80자)을 `display.add_alert()`로 UI 알림 영역에 표시합니다.
- **HTML Parse Mode** 사용을 권장합니다 (Markdown 특수문자 충돌 방지).
- **Retry on Timeout**: `wrap_reply`/`wrap_edit`는 `TimedOut`/`NetworkError` 발생 시 최대 2회 재시도합니다 (1초 간격). 재시도 실패 시 예외를 상위로 전파합니다.
