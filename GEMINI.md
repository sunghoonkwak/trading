# GEMINI.md (AI Strategic Context)

이 파일은 AI 에이전트가 시스템의 기술적 설계와 데이터 흐름을 이해하고 안전하게 코드를 수정하기 위한 가이드입니다.

## 🏗️ Technical Architecture

본 시스템은 고가용성 실시간 매매를 위해 **멀티 스레드 기반의 이벤트 중심 아키텍처**를 채택하고 있습니다.

### 1. 핵심 컴포넌트 및 데이터 흐름
- **KIS Engine (`src/kis/`)**: 
    - `REST API`: 인증, 주문 생성, 잔고 조회 (Request-Response)
    - `WebSocket`: 실시간 호가 및 체결 데이터 수신
    - `Event Pipe`: 수신된 이벤트를 다른 모듈로 전달하는 IPC 채널
- **Core Infrastructure (`src/core/`)**: 시스템 운영에 필요한 핵심 유틸리티(설정, 상수, 통신 규약) 및 웹 대시보드 서버를 관리합니다.
- **State Management (`src/state/`)**: 시장 상태(`market_state`)와 시스템 스레드 상태(`system_state`)를 전역적으로 관리하며 스레드 세이프하게 유지합니다.
- **Strategies (`src/strategy/`)**: 독립된 전략 모듈. `execution_service`를 통해 실제 주문을 집행하며 공통 인터페이스를 공유합니다.
- **Communication Layer**: 
    - `Telegram Bot`: 원격 제어 및 상태 리포팅 (독립 스레드)
    - `Web Server`: `src/core/web_server.py`를 통해 실시간 로그 및 데이터 뷰어 제공

### 2. 기술 스택 상세
- **Language**: Python 3.9+
- **Concurrency**: `threading`, `Event`, `Lock`을 사용한 멀티 스레드 제어
- **Networking**: `requests` (REST), `websockets` (WS), `uvicorn/fastapi` (Web)
- **Data Flow**: `kis_thread` → `event_handler` → `core.display`/`core.web_server`/`telegram` 순으로 이벤트 전파

---

## 📂 디렉토리별 기술적 역할

| 경로 | 역할 및 책임 |
| :--- | :--- |
| `src/core/` | **[핵심]** 전역 상수, 종목 설정, 스레드 통신 규약 및 웹 서버 운영 |
| `src/kis/` | KIS API 연동 최상위 계층. 저수준 통신 처리 및 파이프 서버 운영 |
| `src/kis/kis_api/` | **[수정 금지]** KIS 공식 라이브러리 및 샘플 코드 |
| `src/strategy/` | 매매 로직 추상화 및 구현 (Base 클래스 상속 구조) |
| `src/scheduler/` | `schedule` 라이브러리를 활용한 정기적 배치 작업 (주문 동기화 등) |
| `src/state/` | 시스템 전역 상태 동기화 및 공유 데이터 모델 |
| `src/utils/` | 로깅, 포맷팅, 마켓 캘린더 등 범용 유틸리티 |

---

## 🛠️ 개발 및 작업 가이드

1.  **설계 우선**: 코드 수정 전 반드시 `GEMINI.md`의 아키텍처를 참고하여 시스템 영향도를 분석합니다.
2.  **패키지 구조 준수**: 유틸리티나 설정 관련 모듈 추가 시 `src/core/` 배치를 검토합니다.
3.  **스레드 안전**: 상태 공유 시 `market_state.py`의 접근 방식을 준수하며, 새로운 공유 상태 도입 시 락(Lock) 전략을 검토합니다.
4.  **에러 핸들링**: 통신 장애가 매매 결함으로 이어지지 않도록 예외 처리를 철저히 합니다.

> **주의**: 커밋 규칙, 문서화 양식 등 구체적인 작업 지침은 **`.agent/rules/rules.md`**를 엄격히 따릅니다.
