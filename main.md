# main.md

이 파일은 애플리케이션의 메인 엔트리 포인트입니다. 인증, 로그 로테이션, 웹소켓 통신, Named Pipe 서버, Telegram 봇 및 터미널의 대화형 메뉴를 조율합니다.

## Purpose (목적)

트레이딩 시스템을 초기화하고, 웹소켓 연결의 생명주기를 관리하며, 수동 거래 및 모니터링을 위한 사용자 친화적인 인터페이스를 제공하는 것입니다.

## Startup Flow (시작 흐름)

```
main.py 실행
    ↓
1. 로그 로테이션 (WebSocket_latest.log 백업)
2. requests_cache 비활성화 (스레드 안전성)
3. KIS API 인증 (auth(), auth_ws())
4. Event Pipe 서버 생성
5. Telegram 봇 초기화
6. 메인 메뉴 진입
```

## Function (기능)

### 로그 로테이션 로직 (최상위 코드)
시작 시 기존 `WebSocket_latest.log` 파일의 시간 정보를 확인하고, 백업 본을 생성하여 로그 파일이 무제한으로 커지는 것을 방지합니다. 또한, 시스템 안정성을 위해 전역적으로 설치되었을 수 있는 `requests_cache`를 명시적으로 비활성화(uninstall)하여 멀티스레드 환경에서의 SQLite 충돌을 차단합니다.

#### input
- `WebSocket_latest.log` 파일 존재 여부.

#### output
- 백업된 로그 파일 및 새로 생성된 `WebSocket_latest.log`.

---

### write_cleared
터미널의 현재 줄을 지우고 텍스트를 출력합니다.

#### input
- `text` (str): 출력할 텍스트.
- `end` (str): 줄 바꿈 문자.

#### output
- `None`.

---

### spawn_viewer
Windows Terminal에서 Event Viewer(event_viewer/event_viewer.py)를 별도 탭으로 실행합니다.

#### input
- `None`.

#### output
- `bool`: 성공 여부.

---

### close_viewer
실행 중인 Event Viewer 프로세스를 종료합니다.

#### input
- `None`.

#### output
- `None`.

---

### on_result
웹소켓 메시지에 대한 전역 콜백 함수입니다.

수신된 체결/시세 데이터를 파싱하여 전역 상태를 업데이트합니다.
주문 관련 메시지(체결, 취소 등) 수신 시 해당 항목을 UI에서 즉시 제거(`display.remove_order_state`)하고 알림 영역에 이벤트를 표시합니다.

이후 `request_sync`를 호출하여 1초 뒤에 백그라운드에서 주문 목록을 서버와 최종 동기화합니다. 이 과정에는 디바운싱(Debouncing)이 적용되어 짧은 시간 내 여러 이벤트 발생 시 한 번의 동기화만 수행됩니다.

해외 주문의 경우 `ODER_KIND2` 코드를 분석하여 LOC, 시장가 등 상세 유형을 구분합니다.

#### input
- `ws`: 웹소켓 연결 객체.
- `tr_id` (str): 수신된 데이터의 트랜잭션 ID.
- `df` (DataFrame): 파싱된 주 데이터프레임.
- `dm` (dict): 수신된 전체 데이터 딕셔너리.

#### output
- `None` (상태 업데이트, 로그 전송 및 UI 업데이트).

---

## Telegram Integration (텔레그램 통합)

`main.py`에서 Telegram 봇을 초기화합니다:

```python
# Initialize Telegram bot (runs in background)
try:
    from telegram_bot.telegram_bot import initialize_telegram
    if initialize_telegram():
        add_alert("[TG] Bot started", level="INFO")
    else:
        add_alert("[TG] Failed to start", level="ERROR")
except Exception as e:
    logging.warning(f"[Telegram] Failed to initialize: {e}")
```

Telegram 봇은 별도 스레드에서 실행되며, 메인 프로그램과 독립적으로 동작합니다.

## Related Modules (관련 모듈)

| Module | Description |
|--------|-------------|
| `telegram_bot/telegram_bot.py` | Telegram 원격 제어 |
| `menu/menu.py` | 메인 메뉴 UI |
| `display.py` | 터미널 UI 렌더링 |
| `event_viewer/` | 실시간 이벤트 뷰어 |
