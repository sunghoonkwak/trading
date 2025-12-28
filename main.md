# main.md

이 파일은 애플리케이션의 메인 엔트리 포인트입니다. 인증, 로그 로테이션, 웹소켓 통신, Named Pipe 서버 및 터미널의 대화형 메뉴를 조율합니다.

## Purpose (목적)
트레이딩 시스템을 초기화하고, 웹소켓 연결의 생명주기를 관리하며, 수동 거래 및 모니터링을 위한 사용자 친화적인 인터페이스를 제공하는 것입니다.

## Function (기능)

### 로그 로테이션 로직 (최상위 코드)
시작 시 기존 `WebSocket_latest.log` 파일의 시간 정보를 확인하고, 백업본을 생성하여 로그 파일이 무제한으로 커지는 것을 방지합니다.
#### input
- `WebSocket_latest.log` 파일 존재 여부.
#### output
- 백업된 로그 파일 및 새로 생성된 `WebSocket_latest.log`.

### write_cleared
터미널의 현재 줄을 지우고 텍스트를 출력합니다.
#### input
- `text` (str): 출력할 텍스트.
- `end` (str): 줄 바꿈 문자.
#### output
- `None`.

### spawn_viewer
Windows Terminal에서 Event Viewer(event_viewer.py)를 별도 탭으로 실행합니다.
#### input
- `None`.
#### output
- `bool`: 성공 여부.

### close_viewer
실행 중인 Event Viewer 프로세스를 종료합니다.
#### input
- `None`.
#### output
- `None`.

### on_result
웹소켓 메시지에 대한 전역 콜백 함수입니다.
수신된 체결/시세 데이터를 파싱하여 전역 상태를 업데이트하고,
Named Pipe를 통해 Event Viewer로 로그를 전송하며,
주문 상태를 메인 터미널에 표시합니다.
#### input
- `ws`: 웹소켓 연결 객체.
- `tr_id` (str): 수신된 데이터의 트랜잭션 ID.
- `df` (DataFrame): 파싱된 주 데이터프레임.
- `dm` (dict): 수신된 전체 데이터 딕셔너리.
#### output
- `None` (상태 업데이트, 로그 전송 및 UI 업데이트).
