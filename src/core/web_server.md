# Web Server (`web_server.py`)

## 개요
FastAPI 기반의 경량 웹 서버로, 시스템 이벤트를 실시간으로 웹 브라우저(Event Viewer)에 중계하는 역할을 합니다.
`src/core/` 패키지로 이동되어 시스템의 핵심 서비스 레이어에서 동작하며, **WebSocket**을 통한 실시간 데이터 스트리밍에 집중합니다.

## 주요 기능
1. **WebSocket Streaming**: `/ws` 엔드포인트를 통해 클라이언트와 연결하고 실시간 데이터(주문, 시세, 로그)를 전송합니다.
2. **Event Broadcasting**: `kis.event_pipe`로부터 수신한 메시지를 연결된 모든 웹 클라이언트에게 브로드캐스트합니다.
3. **Static File Serving**: `src/web/` 디렉토리의 정적 파일(`favicon.ico`, `index.html`, `styles.css`, `app.js`)을 제공합니다.
4. **Log Redirection**: Uvicorn 서버의 로그를 표준 출력으로 리다이렉트하여 컨테이너 로그 시스템과 통합합니다.
5. **HTTPS 지원**: `src/certs/` 폴더의 인증서를 통한 SSL/TLS 암호화 연결을 지원합니다.
6. **Holdings Data API**: 특정 종목의 상세 보유 현황을 조회하기 위한 REST API(`/api/holdings/{ticker}`)를 제공합니다.

## 웹 테스트 액션 제어

아래 엔드포인트는 테스트 편의용 운영 액션이므로 기본적으로 비활성화되어 있습니다. 메모 조회 및 삭제 API는 이 설정의 영향을 받지 않습니다.

| 환경변수 | 기본값 | 활성화 대상 |
| --- | --- | --- |
| `WEB_ENABLE_ORDER_CANCEL` | `false` | `POST /api/orders/{order_id}/cancel` |
| `WEB_ENABLE_MANUAL_REPORT_TRIGGERS` | `false` | `POST /api/trigger/portfolio`, `POST /api/trigger/order` |

임시 테스트가 필요할 때만 Docker 환경변수 값을 `true`로 바꿔 활성화합니다. `true`, `1`, `yes`, `on` 값을 활성화로 인식합니다.


## HTTPS/SSL 설정

### 인증서 생성 (예시)
```bash
# 프로젝트 루트(src/의 부모) 기준
mkdir -p src/web/certs
openssl req -x509 -newkey rsa:4096 -keyout src/web/certs/key.pem -out src/web/certs/cert.pem \
  -days 365 -nodes -subj "/CN=localhost/O=Trading/C=KR"
```

### 인증서 위치
- `src/web/certs/cert.pem`: SSL 인증서
- `src/web/certs/key.pem`: 개인 키
- *참고: 웹 서버 자산의 응집도를 높이기 위해 인증서 폴더가 `src/web/certs/`로 이동되었습니다.*

### 동작 방식
- 인증서 파일이 존재하면 자동으로 **HTTPS**로 실행
- 인증서가 없으면 **HTTP**로 fallback
- `use_ssl=False` 파라미터로 강제 HTTP 사용 가능

### 접속 URL
- HTTPS: `https://<server-ip>:8080`
- 브라우저 경고: Self-signed 인증서 사용 시 경고가 표시될 수 있습니다.

## 구성 요소 (주요 변경 사항)

### `BASE_DIR` 상수
모듈의 현재 위치(`src/core/`)로부터 한 단계 상위인 `src/` 디렉토리를 가리킵니다. 이를 통해 `web/`, `certs/` 등 다른 형제 디렉토리의 자산을 안정적으로 참조합니다.

### `favicon()` / `get_index()`
- `src/web/` 폴더 내의 정적 파일을 읽어 반환합니다.
- 정적 파일 폴더 구조:
    - `src/web/index.html`
    - `src/web/favicon.ico`
    - `src/web/static/` (CSS, JS)

### `start_web_server(host, port, use_ssl)`
Uvicorn 서버를 실행합니다.
- `main.py`에서 `core.web_server` 패키지를 통해 임포트되어 별도 스레드로 기동됩니다.
