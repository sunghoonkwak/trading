# Telegram System Commands (`src/interfaces/telegram/system.py`)

Trading runtime 생명주기를 Telegram에서 제어하는 명령 모듈입니다.
`RuntimeController`는 `main.py`가 `RuntimeCommandHandler` factory에 주입하므로,
Telegram 명령은 core callback registry나 module-global 상태에 의존하지 않습니다.

## Core Logic

1. **초기 OFF 안내**: Docker 컨테이너가 시작되면 Telegram bot만 켜지고
   trading runtime은 OFF입니다. 초기 안내 메시지는 `/system_on`과
   `/system_status`만 보여줍니다.
2. **ON 안내**: `/system_on` 성공 뒤에는 기존 portfolio/strategy/rebalance
   명령 목록과 `/system_off`, `/system_status`를 함께 안내합니다.
3. **OFF 상태 차단**: Trading runtime이 OFF이면 runtime이 필요한 명령을
   실행하지 않고 `/system_on` 안내를 보냅니다.

## Commands

- `/system_on`: KIS, Toss, scheduler, web dashboard runtime을 시작합니다.
- `/system_off`: KIS/WebSocket/scheduler runtime을 중지하고 Telegram은
  유지합니다.
- `/system_status`: 현재 trading runtime 상태를 확인합니다.
