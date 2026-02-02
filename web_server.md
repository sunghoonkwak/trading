# Web Server (`web_server.py`)

## 개요
FastAPI 기반의 경량 웹 서버로, 시스템 이벤트를 실시간으로 웹 브라우저(Event Viewer)에 중계하는 역할을 합니다.
**WebSocket**을 통한 단방향 데이터 스트리밍(Server -> Client)에 집중합니다.

## 주요 기능
1. **WebSocket Streaming**: `/ws` 엔드포인트를 통해 클라이언트와 연결하고 실시간 데이터(주문, 시세, 로그)를 전송합니다.
2. **Event Broadcasting**: `kis.event_pipe`로부터 수신한 메시지를 연결된 모든 웹 클라이언트에게 브로드캐스트합니다.
3. **Static File Serving**: `idx.html`, `styles.css`, `app.js` 등 프론트엔드 정적 파일을 제공합니다.
4. **Log Redirection**: Uvicorn 서버의 로그를 `WebSocket_latest.log` 파일로 리다이렉트하여 터미널 출력을 깔끔하게 유지합니다.
5. **HTTPS 지원**: Self-signed 인증서를 통한 SSL/TLS 암호화 연결을 지원합니다.

## HTTPS/SSL 설정

### 인증서 생성
```bash
mkdir -p certs
openssl req -x509 -newkey rsa:4096 -keyout certs/key.pem -out certs/cert.pem \
  -days 365 -nodes -subj "/CN=localhost/O=Trading/C=KR"
```

### 인증서 위치
- `certs/cert.pem`: SSL 인증서
- `certs/key.pem`: 개인 키

### 동작 방식
- 인증서 파일이 존재하면 자동으로 **HTTPS**로 실행
- 인증서가 없으면 **HTTP**로 fallback
- `use_ssl=False` 파라미터로 강제 HTTP 사용 가능

### 접속 URL
- HTTPS: `https://<server-ip>:8080`
- 브라우저 경고: Self-signed 인증서 사용 시 "연결이 안전하지 않음" 경고가 표시됨 (정상)

## 구성 요소 (Class & Functions)

### `ConnectionManager` 클래스
WebSocket 연결을 관리합니다.
- `active_connections`: 현재 연결된 WebSocket 클라이언트 목록 (Set).
- `connect(websocket)`: 새 클라이언트 연결 수락 및 등록.
- `disconnect(websocket)`: 연결 종료 및 목록에서 제거.
- `broadcast(message)`: 모든 연결된 클라이언트에게 메시지 전송. (Thread-safe)

### `_broadcast_callback(msg_type, message)`
`kis.event_pipe`에서 호출되는 콜백 함수입니다.
이벤트를 수신하여 WebSocket 메시지 포맷(`{"type":..., "data":..., "time":...}`)으로 변환 후 브로드캐스트합니다.

### `lifespan(app)`
애플리케이션 시작/종료 시 실행되는 Context Manager입니다.
- **Startup**: `event_pipe.set_web_broadcast_callback`을 통해 브로드캐스트 콜백을 등록합니다.
- **Shutdown**: 리소스 정리.

### `start_web_server(host, port, use_ssl)`
Uvicorn 서버를 실행합니다.
- `host`: 바인딩할 호스트 (기본값: `0.0.0.0`)
- `port`: 포트 번호 (기본값: `8080`)
- `use_ssl`: HTTPS 사용 여부 (기본값: `True`)
- 로그 레벨을 `warning`으로 설정하고 `access_log`를 비활성화하여 불필요한 콘솔 출력을 억제합니다.
- 메인 스레드를 블로킹하므로, `main.py`에서는 이를 별도 스레드로 실행합니다.

## 메시지 타입 (Protocol)
- `ODR`: 주문 체결/변경 내역 (Orders)
- `MKT`: 실시간 시세 (Quotes)
- `SYS`: 시스템 로그 (System Log)
- `ALT`: 알림 및 에러 메시지 (System Log에 표시됨)
- `CLR`: 화면 클리어 명령

## 주문 동기화 (Order Sync)

### `sync_orders_to_client(websocket)`
클라이언트가 `sync_orders` 메시지를 보내면 호출됩니다.
- 현재 미체결 주문을 KIS API에서 조회하여 클라이언트에 전송합니다.
- 페이지 새로고침 시 기존 주문을 표시하는 데 사용됩니다.

### `_fetch_orders_for_sync()`
미체결 주문을 조회하여 WebSocket 메시지 형식으로 변환합니다.
- `menu.handle_manage_orders.fetch_open_orders()` 호출
- 국내/해외 주문을 ODR 형식으로 포맷팅하여 반환
