# event_viewer.md

별도 터미널에서 실행되는 실시간 WebSocket 로그 뷰어입니다. Named Pipe를 통해 메인 프로세스로부터 로그를 수신하여 시각화합니다.

## Purpose (목적)
메인 터미널을 깔끔하게 유지하면서, 종목별 실시간 시세 및 주문 상태를 별도 창에서 모니터링할 수 있게 하는 것입니다.

## UI Layout (화면 구성)

```
============================================================
 Event Viewer (Sticky: 4)
------------------------------------------------------------
[18:00:00] [MKT][삼성전자  ] 005930 | Last: 72,000  ← Sticky 영역
[18:00:00] [MKT][NVDA    ] NVDA   | Last: 140.50  ← (종목별 최신)
------------------------------ History ---------------------
[18:00:10] [SYS] PINGPONG received                 ← History 영역
[18:00:20] [SYS] PINGPONG received                 ← (스크롤 가능)
```

- **Sticky 영역**: 종목별 최신 가격 정보가 고정 표시됩니다.
- **History 영역**: 비종목 로그(PINGPONG 등)가 스크롤 가능하게 쌓입니다.

## Function (기능)

### enable_ansi_colors
Windows 터미널에서 ANSI 색상 코드를 활성화합니다.
#### input
- `None`
#### output
- `None` (콘솔 모드 변경).

### colorize_log
로그 내용에 따라 ANSI 색상을 적용합니다.
#### input
- `log` (str): 로그 메시지.
- `stock_config` (dict): 종목별 색상 설정.
#### output
- `str`: 색상이 적용된 문자열.

### extract_composite_key
로그에서 종목 코드와 유형을 추출하여 복합 키를 생성합니다.
#### input
- `log` (str): 로그 메시지.
#### output
- `str | None`: `"NVDA_MKT"` 형식의 키 또는 None.

### set_scroll_region / reset_scroll_region
ANSI DECSTBM을 사용하여 터미널 스크롤 영역을 설정/해제합니다.
#### input
- `top`, `bottom` (int): 스크롤 영역의 시작/끝 행.
#### output
- `None`.

### draw_sticky_area
헤더와 Sticky 로그를 다시 그립니다.
#### input
- `stock_config` (dict): 종목 색상 설정.
#### output
- `None` (화면 출력).

### append_history_log
History 영역에 로그를 추가합니다.
#### input
- `log` (str): 로그 메시지.
- `stock_config` (dict): 종목 색상 설정.
#### output
- `None` (화면 출력).

### main
Pipe 연결, 화면 초기화, 로그 수신 루프를 실행합니다.
