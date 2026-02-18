# 🚀 KIS Real-time Trading System

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/Docker-Supported-blue.svg)](https://www.docker.com/)

**한국투자증권(KIS) API**를 기반으로 한 고성능 실시간 자동매매 시스템입니다. 현대적인 **웹 대시보드**와 **텔레그램**을 통해 언제 어디서든 자산을 관리하세요.

---

## 💡 주요 특징 (Core Features)

- **⚡ 실시간성**: WebSocket을 통해 호가, 체결, 잔고 변동을 지연 없이 모니터링
- **🖥️ 웹 이벤트 뷰어**: 실시간 로그와 시세를 한눈에 확인하는 다크 모드 UI (`https://localhost:8080`)
- **🤖 스마트 알림**: 주문 체결 내역 및 전략 실행 상태 즉시 텔레그램 전송
- **🛡️ 안정성**: Docker 기반 24시간 중단 없는 매매 환경 및 자동 복구 지향
- **📈 자동 리포트**: 매일 매매 결과와 포트폴리오 상태 자동 요약 및 전송

---

## 📂 프로젝트 구조 (Project Structure)

```text
trading/
├── src/
│   ├── main.py            # 시스템 진입점 (Entry Point)
│   ├── core/              # 핵심 운영 및 설정 모듈 (Constants, Config, Web Server)
│   ├── kis/               # KIS API 연동 및 데이터 파이프라인
│   ├── strategy/          # 매매 전략 추상화 및 구현 (RAOEO, VA, Rebalancing)
│   ├── telegram_bot/      # 텔레그램 대화형 봇 서비스
│   ├── state/             # 시장 및 시스템 전역 상태 관리
│   └── utils/             # 로깅, 포맷팅 등 공용 유틸리티
├── templates/             # 설정 파일 샘플 및 문서 템플릿
├── KIS_config/            # [개인용] API Key 및 비공개 설정 (외부 마운트 권장)
└── docker-compose.yml     # 컨테이너 오케스트레이션
```

---

## 📊 투자 전략 (Investment Strategies)

### 1. RAOEO (무한 매수법)
변동성이 큰 레버리지 ETF(TQQQ, SOXL 등)에 최적화된 코스트 에버리징 전략입니다. 하락장에서 기계적으로 매집하여 반등 시 수익을 확정합니다.

### 2. Value Averaging (목표 가치 적립식)
설정한 목표 가치 경로를 따라 자산 규모를 조절하며 매매하는 스마트 적립식 전략입니다.

### 3. Strategic Rebalancing (자산 배분)
TQQQ(공격)와 SCHD(방어) 등의 자산을 조합하여 변동성을 수확(Volatility Harvesting)하고 MDD를 제어합니다.

---

## 📱 원격 제어 (Telegram Bot)

| 명령어 | 기능 설명 |
| :--- | :--- |
| `/portfolio` | 전체 자산 현황 및 종목별 상세 조회 |
| `/strategy` | RAOEO & VA 전략 통합 조회 및 즉시 실행 |
| `/rebalance` | 자산 배분 리밸런싱 조회 및 즉시 실행 |
| `/daily_report` | 일일 매매 리포트 조회 (예: `/daily_report 20260215`) |
| `/memo` | 최근 1주일간 기록된 투자 메모 조회 (봇에게 메시지 전송 시 자동 저장) |

---

## 🚀 빠른 시작 (Quick Start)

### 1. 환경 설정
프로젝트 외부 경로(`~/KIS_config/`)에 다음 설정 파일들을 준비하세요. (샘플은 `templates/` 참조)
- `kis_devlp.yaml`: KIS API 앱 키 및 계정 정보
- `strategy_config.json`: 전략별 세부 파라미터
- `telegram.txt`: 텔레그램 봇 토큰 및 수신 ID

### 2. 실행 (Docker)
```bash
docker compose up -d --build
docker logs -f my-trading-bot
```

---

## ⚠️ Disclaimer
본 시스템은 투자 보조 도구이며, 모든 투자 책임은 사용자에게 있습니다. 반드시 **모의투자 계좌**에서 충분히 테스트하세요.
