# Runtime Control (`src/core/runtime_control.py`)

Telegram command layer와 `main.TradingSystem` 인스턴스 사이의 얇은 lifecycle
bridge입니다.

## Core Logic

- `TradingSystem.run()`이 Telegram 초기화 후 start/stop/status hook을
  등록합니다.
- Telegram `/system_on`과 `/system_off`는 이 모듈을 통해 현재 실행 중인
  `TradingSystem` 인스턴스에 명령을 전달합니다.
- Hook이 아직 등록되지 않은 상태에서는 실패 결과를 반환하고 예외를
  던지지 않습니다.

## Result

`RuntimeCommandResult`는 명령 성공 여부, 사용자에게 보여줄 메시지,
실패 component, 이미 원하는 상태였는지를 담습니다.
