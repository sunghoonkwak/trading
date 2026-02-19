# Telegram Bot (`src/telegram_bot/telegram_bot.py`)

텔레그램 봇의 초기화, 핸들러 등록, 실행 루프 관리를 담당하는 메인 모듈입니다.
비동기(`asyncio`) 환경에서 `python-telegram-bot`을 실행하며, 별도 스레드에서 폴링을 수행합니다.

# Core Logic (핵심 로직)

1. **자격 증명 로드**: `telegram.txt`에서 토큰과 Chat ID를 읽어옵니다.
2. **비동기 루프 생성**: 메인 스레드와 충돌하지 않도록 별도의 `asyncio` 이벤트 루프를 생성합니다.
3. **핸들러 등록**: 포트폴리오, 전략, 메모 등 기능별 핸들러를 등록합니다.
4. **폴링 시작**: `Application.start_polling()`을 호출하여 메시지를 수신합니다.
5. **초기화 메시지**: 봇이 시작되었음을 알리는 안내 메시지를 전송합니다.

# Key Functions (주요 함수)

## `initialize_telegram`
봇 스레드를 생성하고 시작합니다. 메인 프로세스(`main.py`)에서 호출됩니다.

- **출력 (Output)**: `bool` (성공 여부)
- **중복 방지 (Lock)**: `threading.Lock`과 `_is_initialized` 플래그를 사용하여 중복 실행을 원천 차단합니다.
- **Session ID**: 봇 시작 시 무작위 UUID(8자리)를 생성하여 로그 및 텔레그램 시작 메시지에 표시, 인스턴스 식별을 돕습니다.

## `run_bot` (내부 함수)
실제 비동기 루프를 관리하는 함수입니다. `asyncio.new_event_loop()`를 사용하여 스레드 안전성을 확보합니다.

## `shutdown_telegram`
프로세스 종료 시 봇을 안전하게 정지시키고 종료 메시지를 전송합니다.

# Configuration (`telegram.txt`)

```text
bot_token,chat_id
```

# Usage Example (사용 예시)

```python
from telegram_bot.telegram_bot import initialize_telegram

# 봇 시작 (백그라운드)
initialize_telegram()
```
