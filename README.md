# 🚀 KIS Real-time Trading System

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/Docker-Supported-blue.svg)](https://www.docker.com/)

**한국투자증권(KIS) API**를 기반으로 한 고성능 실시간 자동매매 시스템입니다.  
복잡한 터미널 대신 **현대적인 웹 대시보드**와 **텔레그램**을 통해 언제 어디서든 당신의 자산을 관리하세요.

---

## 🏛️ System Architecture

본 시스템은 안정성과 확장성을 위해 멀티 스레드 기반의 이벤트 중심 아키텍처를 채택하고 있습니다.

- **Core Engine**: KIS REST API & WebSocket을 통한 실시간 데이터 처리
- **Strategies**: 독립된 로직 모듈 (RAOEO, VA, Rebalancing)
- **Monitoring**: FastAPI 기반의 실시간 WebSocket 대시보드 (Event Viewer)
- **Remote Control**: 모듈화된 텔레그램 봇 핸들러를 통한 양방향 통신

---

## 💡 주요 특징 (Core Features)

- **⚡ 실시간성**: WebSocket을 통해 호가, 체결, 잔고 변동을 지연 없이 모니터링합니다.
- **🖥️ 웹 이벤트 뷰어**: 다크 모드 기반의 세련된 UI로 실시간 로그와 시세를 한눈에 확인합니다.
- **🤖 스마트 알림**: 모든 주문 체결 내역이 즉시 텔레그램으로 전송됩니다.
- **🛡️ 안정성**: Docker 컨테이너 환경을 지원하여 24시간 중단 없는 매매 환경을 제공합니다.
- **📈 자동화된 보고**: 매일 매매 결과와 포트폴리오 상태를 자동으로 리포팅합니다.

---

## 📊 투자 전략 (Investment Strategies)

이 시스템은 수학적 확률과 시스템의 힘을 믿는 투자자를 위한 세 가지 핵심 전략을 제공합니다.

### 1. RAOEO (무한 매수법 - Unlimited Buying)
*높은 변동성을 수익으로 전환하는 코스트 에버리징의 극치*
- **전략 핵심**: 변동성이 클수록 수익으로 연결되는 구조입니다. 하락장에서 기계적으로 매집하여 반등 시 수익을 확정합니다.
- **장점**: 충분한 시드가 준비되어 현금 비중을 높게 유지할 수 있을수록 전략적 우위가 강력해지며, 심리적 안정을 제공합니다.
- **적합한 상황**: TQQQ, SOXL 등 변동성이 매우 큰 레버리지 ETF 운용 시.

### 2. Value Averaging (VA - 목표 가치 적립식)
*단순 정액 적립을 넘어선 스마트한 가치 조절 전략*
- **전략 핵심**: 시간이 흐름에 따라 내 자산이 가져야 할 '목표 가치'를 설정하고, 현재 가치와의 괴리만큼 매매합니다.
- **⚠️ 자산 규모의 함정**: 투자 초기에는 평단가 조절 효과가 탁월하지만, **총 투자액(Size)이 커지면** 새로 투입되는 소액의 적립금으로는 전체 평단가를 낮추는 방어 효과가 현저히 떨어집니다. 따라서 자산 규모에 맞는 적절한 투입금 설정이 필수적입니다.
- **적합한 상황**: 자산 형성 초기 단계의 적립식 투자자.

### 3. Strategic Rebalancing (전략적 자산 배분)
*데이터와 시스템이 주도하는 "공짜 점심" 변동성 수확*
- **변동성 수확 (Volatility Harvesting)**: 주가가 제자리걸음을 하더라도, 위아래로 흔들리는 노이즈를 먹고 자랍니다. 고점에서 팔고 저점에서 사는 행위를 무한 반복하여 수량을 늘립니다.
- **MDD 제어 및 생존력**: TQQQ와 같은 공격 자산과 SCHD 같은 방어 자산을 조합하여 폭락장에서도 "저가 매수 기회"로 강제 전환시키는 멘탈 방어막을 제공합니다.
- **절세 및 복리 효과**: 추가 현금 흐름(입금)이 있다면 매도 없이 **'입금'만으로 비중을 조절**할 수 있습니다. 이는 양도세(22%) 발생을 이연시켜 복리 효과를 극대화합니다.

| 투자 방식 | 무지성 존버 | 단타/스윙 | **전략적 리밸런싱 (Bot)** |
| :--- | :--- | :--- | :--- |
| **의사결정** | 감정 (공포/탐욕) | 차트/감 | **데이터 (JSON 설정값)** |
| **하락장 대응** | 기도/방치 | 손절 (뇌동매매) | **기계적 추매 (자동)** |
| **자본 효율** | 낮음 | 보통 | **최상 (현금/주식 최적화)** |

---

## 📱 Interface & Remote Control

### 🌐 Web Dashboard (Event Viewer)
브라우저에서 실시간으로 시스템 상태를 확인하세요 (`http://localhost:8080`).
- **좌측**: 주문 내역(Orders), 실시간 시세(Quotes), 메모(Memos)
- **우측**: 시스템 전체 로그(System Log)를 실시간 스트리밍

### 🤖 Telegram Bot Commands
텔레그램을 통해 외부에서도 완벽하게 제어할 수 있습니다.

| 명령어 | 기능 설명 |
| :--- | :--- |
| **💰 자산 조회** | |
| `/portfolio` | 전체 포트폴리오 현황 및 종목별 상세 조회 (인터랙티브) |
| `/portfolio_weight` | 현재 비중과 목표 비중 비교 및 리밸런싱 제안 |
| `/placed_orders` | 현재 미체결 주문 목록 확인 |
| **📈 전략 실행** | |
| `/strategy` | **RAOEO & VA** 전략 통합 조회 및 즉시 주문 실행 |
| `/rebalance` | **TQQQ+SCHD** 리밸런싱 전략 조회 및 즉시 주문 실행 |
| **📋 기록 및 보고** | |
| `/daily_report` | 일일 매매 리포트 아카이브 조회 (`/daily_report 20260215`) |
| `/memo` | 최근 1주일간 기록된 투자 메모 일괄 조회 |
| *(일반 메시지)* | 봇에게 메시지를 보내면 자동으로 날짜별 **투자 메모**로 저장됩니다. |

---

## 🚀 Quick Start

### 1. 환경 설정 (Setup)
보안을 위해 설정 파일은 프로젝트 외부(`~/KIS_config/`)에서 관리합니다. `templete/` 디렉토리를 참조하세요.

| 파일명 | 용도 | 주요 설정 항목 |
| :--- | :--- | :--- |
| **kis_devlp.yaml** | KIS API 인증 | 앱 키, 계정 번호, 접속 도메인 |
| **strategy_config.json** | 통합 전략 설정 | RAOEO/VA/Rebalancing 세부 파라미터 |
| **telegram.txt** | 텔레그램 알림 | 봇 토큰 및 수신용 채팅 ID |

### 2. 실행 (Run with Docker)
```bash
docker compose up -d --build
docker logs -f my-trading-bot
```

---

## ⚠️ Disclaimer
본 시스템은 투자 보조 도구일 뿐이며, 투자에 대한 모든 책임은 사용자 본인에게 있습니다. 반드시 **모의투자 계좌**에서 충분한 테스트를 거친 후 실전에 적용하시기 바랍니다.
