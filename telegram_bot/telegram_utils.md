# telegram_utils.py

이 모듈은 Telegram 봇에서 공통으로 사용되는 메시징 래퍼 함수들을 제공합니다.
순환 참조 방지를 위해 `telegram_bot.py`에서 분리되었습니다.

## Functions (함수)

### wrap_reply
`update.message.reply_text`를 래핑하여 메시지 전송과 동시에 UI 알림을 추가합니다.

```python
await wrap_reply(update, "메시지 내용", parse_mode='HTML')
```

---

### wrap_edit
`update.callback_query.edit_message_text`를 래핑합니다. InlineKeyboard 상호작용에 사용됩니다.

```python
await wrap_edit(update, "수정된 메시지", parse_mode='HTML')
```

---

### wrap_send
`bot.send_message`를 래핑하여 사용자 상호작용 없이 직접 메시지를 전송합니다.
전역으로 설정된 `_bot`과 `_chat_id`를 사용합니다.

```python
await wrap_send("알림 메시지", parse_mode='HTML')
```

---

### wrap_edit_message
`bot.edit_message_text`를 래핑합니다. 메시지 ID를 직접 지정하여 기존 메시지를 수정합니다.
타임아웃 핸들러 등에서 `update` 객체 없이 메시지를 수정할 때 사용합니다.

```python
await wrap_edit_message(chat_id, message_id, "수정 내용", parse_mode='HTML')
```

---

### set_telegram_bot
봇 초기화 시 호출되어 `wrap_send`, `wrap_edit_message`에서 사용할 봇 인스턴스와 채팅 ID를 설정합니다.

```python
set_telegram_bot(app.bot, chat_id)
```

## Technical Notes

- 모든 래퍼 함수는 메시지의 첫 줄(최대 80자)을 `display.add_alert()`로 UI 알림 영역에 표시합니다.
- **HTML Parse Mode** 사용을 권장합니다 (Markdown 특수문자 충돌 방지).
