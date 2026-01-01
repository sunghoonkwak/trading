# telegram_bot.py

이 모듈은 Telegram bot을 통한 원격 트레이딩 제어 기능을 제공하는 코어 패키지입니다.

## Structure (구조)

- `telegram_bot.py`: 봇 초기화, 자격 증명 로드, 공통 메시징 래퍼 (`Core`)
- `telegram_raoeo.py`: RAOEO 전략 전용 명령어 및 리포트 핸들러 (`Strategy`)
- `__init__.py`: 패키지 노출 정의

## Dependencies (의존성)

```bash
pip install python-telegram-bot
```

## Configuration (설정)

`telegram.txt` 파일에 다음 형식으로 저장:
```
BOT_TOKEN,CHAT_ID
```

## Public API (`telegram_bot.py`)

### initialize_telegram
텔레그램 봇을 초기화하고 백그라운드 스레드에서 폴링을 시작합니다. 등록된 각 전략 모듈의 핸들러를 자동으로 추가합니다. 초기화 시 시스템 시작 메시지를 전송합니다.

### shutdown_telegram
프로그램이 정상 종료될 때(`q` 입력 시) 사용자에게 하차 알림을 전송합니다. 종료 프로세스를 방해하지 않도록 동기 HTTP 요청(`requests`)과 짧은 타임아웃을 사용합니다.

### wrap_reply / wrap_send
메시지를 텔레그램으로 전송함과 동시에, 메시지의 첫 줄을 시스템 UI 알림(Alert) 영역에 표시합니다. 비동기로 동작하며, 특수 문자 충돌 방지를 위해 기본적으로 **HTML Parse Mode**를 사용합니다.

### load_telegram_credentials
`telegram.txt` 파일로부터 봇 토큰과 채팅 ID를 로드합니다.

## Extensibility (확장성)
새로운 트레이딩 전략을 텔레그램에 추가하려면 다음 단계를 따릅니다:
1. `telegram_전략명.py` 모듈 생성
2. 명령어 핸들러 정의 및 `register_전략명_handlers(app)` 구현
3. `telegram_bot.py`의 `initialize_telegram`에서 해당 등록 함수 호출

## Usage Example

```python
from telegram_bot import initialize_telegram

# 프로그램 시작 시 호출
if initialize_telegram():
    print("Telegram bot started")
```
