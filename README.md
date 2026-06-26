# KIS/Toss Real-Time Trading System

Korea Investment Securities(KIS)와 Toss Invest API 기반의 실시간 자동매매
시스템입니다. Docker 컨테이너 안에서 KIS REST/WebSocket, Toss REST helper,
전략 실행, 스케줄러, Telegram 봇, FastAPI 웹 대시보드를 함께 구동합니다.

이 프로젝트는 개인 실거래 운영을 염두에 둔 도구입니다. 처음 실행하거나
전략 설정을 바꿀 때는 반드시 모의투자 또는 충분히 작은 규모로 검증하세요.

## 현재 구성 요약

- KIS REST API 인증, 잔고 조회, 미체결 주문 조회/취소, 국내/해외 주문 실행
- KIS WebSocket 기반 체결/호가 이벤트 수신 및 실시간 상태 캐시
- Toss Invest 토큰 초기화, 포트폴리오/매수가능금액/현재가/미체결 주문 조회
- `strategy_broker` 설정에 따른 KIS 또는 Toss 전략 주문 실행
- RAOEO, Value Averaging, Rebalancing 전략 계산 및 실행
- 매일 포트폴리오/전략 리포트 생성 및 Telegram 전송
- 미국장 시간대 주기적 리밸런싱 점검
- 웹 대시보드에서 이벤트, 주문, 메모, 보유 종목 상세 조회
- Google Sheets 포트폴리오 데이터 병합 지원
- `scripts/backtest/raoeo/` 기반 RAOEO 백테스트 도구

## 중요한 운영 원칙

런타임은 Docker 전용입니다. `src/main.py`는 `ENV_MODE=docker`가 아니면
시작하지 않도록 막혀 있으므로 호스트에서 직접 실행하지 마세요.

개발용 테스트와 유틸리티는 호스트의 가상환경을 사용합니다.

```bash
venv/bin/python
venv/bin/pytest
```

운영 설정과 비밀값은 저장소 밖의 `~/KIS_config`에 둡니다. 이 저장소의
`templates/`는 예시 파일만 제공합니다.

## 프로젝트 구조

```text
trading/
├── src/
│   ├── main.py                  # Docker 런타임 엔트리포인트
│   ├── core/                    # 상수, 설정, 웹 서버, 락, 표시 상태
│   ├── kis/                     # KIS REST/WebSocket, 공식 API 래퍼
│   ├── toss/                    # Toss Invest Open API helper
│   ├── broker/                  # KIS/Toss facade와 전략 broker 선택
│   ├── strategy/                # RAOEO, VA, 리밸런싱, 실행 서비스
│   ├── scheduler/               # 정기 리포트와 주기적 리밸런싱 작업
│   ├── telegram_bot/            # Telegram 명령어와 알림
│   ├── data/                    # 설정/포트폴리오 데이터 로딩과 비중 계산
│   ├── state/                   # 시장/시스템 상태 캐시
│   ├── utils/                   # 로깅, 포맷, 시장 시간 유틸리티
│   └── web/                     # 웹 대시보드 정적 파일과 인증서 위치
├── templates/                   # 운영 설정 예시
├── scripts/backtest/raoeo/      # RAOEO 백테스트와 분석 산출물
├── tests/                       # pytest 테스트
├── docker-compose.yml           # Docker 운영 정의
├── Dockerfile                   # Python 3.11 런타임 이미지
└── requirements.txt             # Python 의존성
```

## 설정 파일

기본 설정 루트는 `~/KIS_config`입니다. 컨테이너에서는 `HOME=/app`으로
실행되므로 코드가 `/app/KIS_config`를 읽고, 로컬 운영에서는 보통 호스트의
`~/KIS_config`를 그 위치로 마운트합니다.

`docker-compose.yml`의 볼륨은 현재 특정 사용자 경로로 되어 있을 수
있습니다. 다른 환경에서 실행할 때는 왼쪽 호스트 경로를 본인 환경에 맞게
바꾸세요.

```yaml
volumes:
  - ${HOME}/KIS_config:/app/KIS_config
```

주요 파일은 다음과 같습니다.

| 파일 | 용도 | 비고 |
| --- | --- | --- |
| `kis_devlp.yaml` | KIS 계좌, 도메인, product code 등 기본 설정 | `templates/kis_devlp.yaml` 참고 |
| `credentials.enc` | KIS app key/secret, HTS ID, 선택적 Toss client id/secret 암호화 파일 | `password.txt`로 복호화 |
| `password.txt` | `credentials.enc` 복호화 비밀번호 | 절대 커밋 금지 |
| `telegram.txt` | Telegram bot token, chat id | `token,chat_id` 형식 |
| `strategy_config.json` | RAOEO, VA, 리밸런싱 전략 설정 | `scripts/validate_config.py`로 검증 |
| `portfolio_weights.json` | 포트폴리오 목표 비중과 그룹 설정 | `/portfolio_weight`, 대시보드 비중 계산 |
| `service-account.json` | Google Sheets 연동 서비스 계정 | 선택 기능 |
| `memo.json` | Telegram/web 메모 저장소 | 없으면 기본값으로 시작 가능 |
| `portfolio.json` | 최근 포트폴리오 캐시 | 런타임 생성 |
| `strategy_history.json` | 전략 실행 이력 | 런타임 생성 |
| `TOSSYYYYMMDD_HHMMSS.json` | Toss access token 캐시 | 런타임 생성 |

KIS 인증 코드는 `kis_devlp.yaml`을 읽은 뒤 `credentials.enc`에서 app key,
app secret, HTS ID를 복호화합니다. Toss 기능을 사용하려면 같은
`credentials.enc`에 Toss client id와 client secret도 포함되어야 합니다.
예시 YAML의 app key 값만 채우는 방식이 아니라 암호화 파일도 필요합니다.

## 빠른 시작

1. 설정 디렉터리를 준비합니다.

```bash
mkdir -p ~/KIS_config
```

2. `templates/`의 예시를 참고해 운영 파일을 만듭니다.

```bash
cp templates/kis_devlp.yaml ~/KIS_config/kis_devlp.yaml
cp templates/strategy_config.json ~/KIS_config/strategy_config.json
cp templates/portfolio_weights.json ~/KIS_config/portfolio_weights.json
```

3. `telegram.txt`, `password.txt`, `credentials.enc`를 준비합니다.
   Toss를 활성화한 현재 런타임은 시작 시 Toss 토큰 초기화에도 성공해야
   스케줄러와 웹 서버를 시작합니다.

4. 전략 설정을 검증합니다.

```bash
venv/bin/python scripts/validate_config.py
```

5. 컨테이너를 빌드하고 실행합니다.

```bash
docker compose up -d --build
docker logs -f my-trading-bot
```

6. 웹 대시보드에 접속합니다.

인증서가 없으면 HTTP로 시작합니다.

```text
http://localhost:8080
```

`src/web/certs/cert.pem`과 `src/web/certs/key.pem`이 있으면 HTTPS로
시작합니다.

```text
https://localhost:8080
```

## 실행 순서

`src/main.py`는 다음 순서로 시스템을 시작합니다.

1. 로그 초기화
2. Docker 환경 여부 확인
3. 중복 실행 방지 락 획득
4. Telegram 봇 초기화
5. KIS REST 인증과 WebSocket approval key 발급
6. KIS WebSocket 및 이벤트 파이프 초기화
7. 미체결 주문 동기화(KIS/Toss)
8. Toss access token 준비
9. 스케줄러 시작
10. 웹 대시보드 시작

Telegram, KIS, Toss 중 하나라도 핵심 초기화가 실패하면 스케줄러와 웹
서버를 시작하지 않고 종료합니다. KIS 또는 Toss 실패는 가능한 경우
Telegram 알림을 먼저 시도합니다. 이는 인증, 알림, 시장 데이터가
불완전한 상태에서 자동 실행이 진행되는 것을 막기 위한 fail-closed
동작입니다.

## 웹 대시보드

웹 서버는 FastAPI와 Uvicorn으로 실행되며 기본 포트는 `8080`입니다.

주요 기능:

- `/ws`: 실시간 이벤트 WebSocket
- `/api/holdings/{ticker}`: 특정 종목 보유 현황 조회
- `/api/memos`: 메모 조회
- `/api/memos/delete`: 메모 삭제
- WebSocket `sync_orders`: 미체결 주문 동기화
- `/api/orders/{order_id}/cancel`: 미체결 주문 취소
- `/api/trigger/portfolio`: 포트폴리오 리포트 수동 실행
- `/api/trigger/order`: 전략/주문 리포트 수동 실행

위험도가 있는 제어 API는 기본적으로 꺼져 있습니다.

| 환경 변수 | 기본값 | 영향 |
| --- | --- | --- |
| `WEB_ENABLE_ORDER_CANCEL` | `false` | 웹에서 주문 취소 허용 |
| `WEB_ENABLE_MANUAL_REPORT_TRIGGERS` | `false` | 웹에서 리포트 수동 실행 허용 |

필요할 때만 `docker-compose.yml`에서 명시적으로 켜세요.

## Telegram 명령어

Telegram 봇은 시작 시 polling 방식으로 실행되며 `~/KIS_config/telegram.txt`를
읽습니다.

| 명령어 | 기능 |
| --- | --- |
| `/portfolio` | 포트폴리오 조회와 종목별 상세 확인 |
| `/portfolio_weight` | 목표 비중 대비 리밸런싱 제안 |
| `/placed_orders` | 현재 미체결 주문 목록 조회 |
| `/strategy` | RAOEO와 VA 전략 조회 및 실행 |
| `/rebalance` | 리밸런싱 전략 조회 및 실행 |
| `/daily_report [YYYYMMDD]` | 저장된 일일 리포트 조회 |
| `/memo` | 최근 1주일 메모 조회 |

명령어가 아닌 일반 텍스트 메시지는 메모로 저장됩니다.

## 스케줄러

스케줄러는 컨테이너 내부의 `Asia/Seoul` 시간대를 기준으로 실행됩니다.

| 작업 | 시각/주기 | 설명 |
| --- | --- | --- |
| 포트폴리오 리포트 | 매일 07:00 KST | 일요일은 건너뜀. 월요일은 최근 저장 리포트를 재전송 |
| 주문/전략 리포트 | 07:00 US/Eastern에 대응하는 KST | RAOEO와 VA를 실행하고 결과 전송 |
| 리밸런싱 점검 | 5분마다 | 09:40-15:40 US/Eastern 구간에서만 실행 |
| DST 재계산 | 매일 00:05 KST | 미국 서머타임 변화에 맞춰 주문 리포트 시간을 재등록 |

리포트 백업은 `~/KIS_config/portfolio_history/` 아래에 저장됩니다.

## 전략

### RAOEO

`strategy_config.json`의 `raoeo.targets`에 정의된 종목별 phase 배열을 따라
매수/매도 주문을 계산합니다. `normal`, `average`, `filling` 매수 타입과
`LOC`, `Limit` 매도 타입을 조합할 수 있습니다.

`cash_ticker`가 설정되어 있고 매수 예산이 부족하면 보유 중인 현금성 ETF를
먼저 매도하는 주문을 생성합니다. 매도 수량은 실제 보유 수량으로 제한됩니다.

### Value Averaging

목표 가치 경로와 현재 평가금액의 차이를 기반으로 매수/매도 주문을 계산합니다.
진행 일차와 실행 이력은 `strategy_history.json`을 통해 추적합니다.

### Rebalancing

목표 자산 비중과 현재 평가금액 차이를 계산해 리밸런싱 주문을 생성합니다.
RAOEO 등 다른 전략에 필요한 예약 현금을 고려해 주문 규모를 조정합니다.

## 데이터 흐름

포트폴리오 데이터는 KIS API, Toss API, Google Sheets 데이터를 scope별로
조회하고 병합해 사용합니다. `scope="all"`은 전체 자산 확인용으로
KIS/GSheet/Toss를 통합하며, Toss API 실패 시 Google Sheets의 `토스`
계정 데이터를 fallback으로 유지합니다. 전략 실행은 `strategy_config.json`의
`strategy_broker` 값에 따라 `kis` 또는 `toss` scope만 조회해 주문 판단에
불필요한 원천을 섞지 않습니다.

가격 데이터는 우선 WebSocket 기반 `state.market_state` 캐시와 보유 잔고의
`cur_price`를 사용하고, 필요한 종목은 Toss 다건 현재가 조회 후 누락분만
KIS REST 가격 조회로 보완합니다.

## 테스트와 검증

호스트 개발 환경에서는 가상환경을 먼저 사용합니다.

```bash
venv/bin/pytest tests
```

컨테이너 안에서 검증하려면 다음 명령을 사용합니다.

```bash
docker compose exec trading-bot python -m pytest tests
```

전략 설정 검증:

```bash
venv/bin/python scripts/validate_config.py
```

RAOEO 단일 백테스트:

```bash
venv/bin/python scripts/backtest/raoeo/backtest_raoeo.py
```

RAOEO 배치 백테스트:

```bash
venv/bin/python scripts/backtest/raoeo/batch_backtest.py
```

## 보안 주의

- API key, app secret, HTS ID, Toss client id/secret, 계좌번호, Telegram
  token, Google service account, `credentials.enc`, `password.txt`, 로그
  파일은 커밋하지 마세요.
- 웹 주문 취소와 수동 리포트 실행 API는 기본 비활성 상태로 유지하세요.
- 설정 변경 후에는 `scripts/validate_config.py`, 단위 테스트, 모의투자 또는
  소액 운용으로 검증하세요.
- 이 저장소에는 개인 운영 환경에 맞춘 값이 남아 있을 수 있습니다. 새 환경에
  배포하기 전 `docker-compose.yml`, `templates/`, `src/stock_configuration.json`
  내용을 반드시 검토하세요.

## 알려진 특이점

- Docker 런타임은 Python 3.11 이미지를 사용합니다. 호스트 개발 환경은
  저장소의 `venv/`를 기준으로 합니다.
- KIS 포트폴리오/가격 조회 래퍼는 일부 테스트에서 paper flag가 켜져 있어도
  `env_dv="real"`을 사용하도록 검증합니다. 실전/모의 전환 정책을 바꿀 때는
  이 동작을 먼저 확인해야 합니다.
- `templates/telegram.txt`는 형식 예시일 뿐입니다. 실제 token이나 chat id를
  저장소에 넣지 마세요.
- 루트에 `LICENSE` 파일이 없으므로 README에 라이선스 배지를 두지 않습니다.

## 면책

이 시스템은 투자 판단과 주문 실행을 보조하는 개인 자동화 도구입니다. 모든
투자 손익과 주문 결과의 책임은 사용자에게 있습니다.
