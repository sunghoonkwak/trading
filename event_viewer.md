# event_viewer.md

별도 터미널에서 실행되는 실시간 WebSocket 로그 뷰어입니다. Named Pipe를 통해 메인 프로세스로부터 로그를 수신하여 시각화합니다.

## Purpose (목적)
메인 터미널을 깔끔하게 유지하면서, 종목별 실시간 시세 및 주문 상태를 별도 창에서 모니터링할 수 있게 하는 것입니다.

## UI Layout (화면 구성)

```
============================================================
 Event Viewer
------------------------------------------------------------
09:29:30|MKT|삼성전자  |005930|Bid: 119,400|Last: 119,500|...  ← Sticky 영역
09:29:30|MKT|SK하이닉스|000660|Bid: 631,000|Last: 631,000|...  ← (종목별 최신, 순서 고정)
09:29:30|MKT|삼성증권  |016360|Bid:  75,500|Last:  75,500|...
------------------------------------------------------------
09:29:29|MKT|삼성전자  |005930|Bid: 119,400|Last: 119,500|...  ← History 영역
09:29:29|MKT|삼성전자  |005930|Bid: 119,400|Last: 119,450|...  ← (스크롤 가능)
```

- **Sticky 영역**: 종목별 최신 가격 정보가 고정 위치에 표시됩니다. 순서는 처음 등록된 순서를 유지합니다.
- **History 영역**: 모든 로그가 시간순으로 스크롤되며 표시됩니다. ANSI scroll region을 사용하여 sticky 영역을 보호합니다.

## Log Format (로그 형식)

로그는 파이프(`|`) 구분자를 사용합니다:
```
HH:MM:SS|TYPE|NAME|TICKER|DATA...
```

- **TYPE**: `MKT` (시세), `ODR` (주문), `EXE` (체결), `COR` (정정), `CAN` (취소), `REJ` (거부)
- **NAME**: 종목명 (10자 고정폭)
- **TICKER**: 종목 코드

## Function (기능)

### enable_ansi_colors
Windows 터미널에서 ANSI 색상 코드를 활성화합니다.

### colorize_log
로그 내용에 따라 ANSI 색상을 적용합니다.
- 종목별 RGB 색상: `stock_configuration.json`에서 정의
- 오류(ERROR, REJ): 빨간색
- 시세(MKT): 회색
- 주문/체결(ODR, EXE): 녹색
- 기타: 노란색

### extract_composite_key
로그에서 종목 코드와 유형을 추출하여 복합 키를 생성합니다.
- 입력: `"09:29:30|MKT|삼성전자|005930|..."`
- 출력: `"005930_MKT"` 또는 `None`

### set_scroll_region / reset_scroll_region
ANSI DECSTBM 시퀀스를 사용하여 터미널 스크롤 영역을 설정/해제합니다.
- History 영역만 스크롤되고, Sticky 영역은 고정됩니다.

### draw_header
헤더를 한 번만 그립니다 (프로그램 시작 시).

### draw_sticky_area
Sticky 로그들을 각각의 고정 위치에 덮어씁니다.
- 순서는 처음 등록된 순서 유지 (move_to_end 미사용)
- Rate limiting: 100ms마다 최대 1번 갱신

### append_history_log
History 영역에 로그를 추가합니다.
- Scroll region 내에서 스크롤됩니다.

### main
Pipe 연결, 화면 초기화, 로그 수신 루프를 실행합니다.

## Debug (디버깅)

`viewer_debug.log` 파일에 다음 정보가 기록됩니다:
- 수신된 이벤트와 추출된 키
- Sticky dict 업데이트 정보
- Sticky 영역 그리기 정보

## Dependencies (의존성)

- `event_pipe`: Named Pipe 통신
- `stock_configuration.json`: 종목별 색상 설정
