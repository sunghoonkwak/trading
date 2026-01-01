# menu.md

이 모듈은 통합 트레인딩 시스템의 대화형 메인 메뉴를 관리하며, 각 하위 핸들러(`account`, `order`, `manage`)를 조율하고 전역 디버그 설정을 제어합니다.

## Purpose (목적)
사용자로부터 메인 메뉴 입력을 수신하여 적절한 작업 핸들러로 제어를 전달하고, 시스템 전체의 디버깅 모드(`ka._DEBUG`)를 중앙에서 관리하는 허브 역할을 합니다.

## Workflow (동작 프로세스)

1.  **Initialize**: `menu()` 호출 시 화면을 초기화하고 `MENU_DEBUG` 플래그를 확인합니다.
2.  **Debug Setup**: `MENU_DEBUG`가 `True`인 경우 `kis_api.kis_auth._DEBUG`를 활성화하여 모든 네트워크 요청/응답 로그를 기록합니다.
3.  **Lazy Loading**: 순환 참조를 방지하기 위해 각 메뉴 핸들러를 함수 실행 시점에 임포트합니다.
4.  **Interaction Loop**: 사용자로부터 입력을 받아 핸들러를 실행합니다.

## Menu Options (메뉴 옵션)

| Key | Action |
|-----|--------|
| `1` | 계좌 정보 (잔고 & 포트폴리오) |
| `2` | 주문 (매수/매도) |
| `3` | 미체결 주문 관리 (정정/취소) |
| `r` | RAOEO Strategy (무한 매수법) |
| `p` | Portfolio (포트폴리오) |
| `0` | 로그 레벨 변경 (INFO → DEBUG → ERROR 순환, menu display에 미표기) |
| `c` | 화면 초기화 및 강제 주문 동기화 (알림 이력은 유지됨) |
| `v` | Event Viewer 열기(menu display에 미표기) |
| `q` | 종료 (Viewer 종료 및 Telegram 종료 알림 전송) |

## Global Configuration (전역 설정)

### MENU_DEBUG
- **Type**: `bool`
- **Description**: 전체 메뉴 시스템의 디버깅 활성화 여부를 결정합니다.
- **Effect**: `True` 설정 시 KIS API 트레이스 및 각 핸들러의 데이터 매핑 상세 로그가 기록됩니다.

## Function (기능)

### menu
애플리케이션의 메인 키보드 인터랙션 루프입니다.
#### input
- 사용자 키보드 입력.
#### output
- `None` (각 하위 핸들러 호출).
