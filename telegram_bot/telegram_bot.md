# telegram_bot.md

이 파일은 Telegram bot을 통한 원격 트레이딩 제어 기능을 구현하는 모듈입니다.

## Purpose (목적)

구동중인 PC에 직접 접근이 불가한 상황에서 Telegram을 통해 다음 기능을 제공합니다:
- RAOEO 전략 상태 조회
- 원격 주문 실행
- 시스템 알림 수신

## Dependencies (의존성)

```bash
pip install python-telegram-bot
```

## Configuration (설정)

`telegram.txt` 파일에 다음 형식으로 저장:
```
BOT_TOKEN,CHAT_ID
```

예시:
```
1234567890:ABCdefGHIjklMNOpqrsTUVwxyz,8491232838
```

## Commands (명령어)

| Command | Description |
|---------|-------------|
| `/raoeo_report` | 현재 RAOEO 전략 상태 조회 (캐시 저장) |
| `/raoeo_order` | 캐시된 주문 실행 |

## Functions (함수)

### load_telegram_credentials
Telegram bot token과 chat ID를 `telegram.txt`에서 로드합니다.

#### Returns
- `tuple[str, str]`: (bot_token, chat_id)

---

### format_telegram_message
`build_raoeo_report()` 결과를 Telegram 메시지 형식으로 변환합니다.

#### Args
- `report` (dict): `build_raoeo_report()` 반환값

#### Returns
- `str`: Markdown 형식의 Telegram 메시지

---

### send_notification
Telegram으로 알림 메시지를 전송합니다.

#### Args
- `message` (str): 전송할 메시지

#### Returns
- `bool`: 전송 성공 여부

---

### async cmd_raoeo_report
`/raoeo_report` 명령어 핸들러. RAOEO 상태를 조회하고 결과를 캐시합니다.

#### Flow
1. `build_raoeo_report()` 호출
2. `current_result`를 모듈 변수에 캐시 (이후 `/raoeo_order`에서 사용)
3. 포맷팅된 메시지를 Telegram으로 전송

---

### async cmd_raoeo_order
`/raoeo_order` 명령어 핸들러. 캐시된 주문을 실행합니다.

#### Flow
1. 오늘 이미 실행되었는지 확인
2. 캐시된 `current_result` 확인
3. `execute_orders()` 호출하여 주문 실행
4. `save_history()`로 결과 저장
5. 실행 결과를 Telegram으로 전송

#### Error Cases
- 이미 오늘 실행됨: "Already executed today"
- 캐시 없음: "Not calculated. Use /raoeo_report first"
- 주문 없음: "No orders to execute"

---

### initialize_telegram
Telegram bot을 초기화하고 백그라운드 스레드에서 polling을 시작합니다.

#### Returns
- `bool`: 초기화 성공 여부

#### Behavior
1. `telegram.txt`에서 credentials 로드
2. 별도 스레드에서 bot polling 시작
3. 초기화 완료 시 Telegram으로 init 메시지 전송

## Module State (모듈 상태)

| Variable | Type | Description |
|----------|------|-------------|
| `_app` | `Application` | Telegram bot Application 인스턴스 |
| `_bot_token` | `str` | Bot API token |
| `_chat_id` | `str` | Target chat ID |
| `_cached_result` | `dict` | `/raoeo_report`에서 캐시된 주문 정보 |

## Usage Example

```python
from telegram_bot.telegram_bot import initialize_telegram

# 프로그램 시작 시 호출
if initialize_telegram():
    print("Telegram bot started")
else:
    print("Failed to start Telegram bot")
```
