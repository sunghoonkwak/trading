# 자동 거래 시스템 (KIS OpenAPI Trading System)

## 1. 목적 (Objective)
한국투자증권(KIS) OpenAPI를 활용하여 실시간 시세 조회 및 자동 매매를 수행하는 통합 트레이딩 시스템입니다. 국내 주식 및 미국 주식(NASDAQ, NYSE, AMEX)의 실시간 시세 수신 및 계좌 통합 관리를 목표로 합니다.

## 2. 폴더 구조 (Folder Tree)

```text
.
├── main.py (main.md)                                         ## 엔트리 포인트 및 메인 컨트롤러
├── menu/                                                     ## 대화형 메뉴 핸들러 패키지
│   ├── menu.py (menu.md)                                     ## 메인 메뉴 컨트롤러 및 전역 디버그 설정
│   ├── handle_place_order.py (handle_place_order.md)         ## 주문 실행 핸들러
│   ├── handle_manage_orders.py (handle_manage_orders.md)     ## 미체결 주문 관리 핸들러
│   └── handle_account_info.py (handle_account_info.md)       ## 계좌 조회 및 데이터 통합
├── display.py (display.md)                                   ## 터미널 UI 및 컬러 로그 시스템 (출력 전담)
├── portfolio.py (portfolio.md)                               ## 통합 포트폴리오 관리 및 CSV 내보내기
├── trading_config.py (trading_config.md)                     ## 설정 및 종목 정보 관리
├── trading_state.py (trading_state.md)                       ## 전역 실행 상태 매니저
├── tests/                                                    ## 유닛 테스트 폴더
├── kis_api/                                                  ## KIS API 특화 패키지
│   ├── domestic_stock/                                       ## 국내 주식 관련 모듈
│   ├── overseas_stock/                                       ## 해외 주식 관련 모듈
│   ├── key/                                                  ## 보안 및 암호화 유틸리티
│   │   ├── key.py (key.md)                                   ## 암호화 및 도구 라이브러리
│   │   ├── generate_credentials.py (generate_credentials.md) ## 인증정보 생성 유틸리티
│   │   └── validate_credentials.py (validate_credentials.md) ## 인증정보 검증 유틸리티
│   └── kis_auth.py                                           ## 인증 및 통신 코어
├── stock_configuration.json                                  ## 실시간 시세 관련 종목 설정 (색상, 활성여부 등)
├── portfolio.json                                            ## 통합 포트폴리오 데이터 (Git 제외)
├── credentials.enc                                           ## 암호화된 API 키 저장소
└── openapi_trading.md                                        ## 프로젝트 메인 문서
```

## 3. 주요 기능 (Key Features)

- **보안 강화**: API 키 암호화 보관 및 실행 시 비밀번호 인증.
- **통합 트레이딩**: 국내/해외 주식 통합 주문 인터페이스 및 잔고 조회.
- **실시간 모니터링**: 웹소켓 기반의 실시간 시세 및 체결 통보, 스마트 로그 고정 기능.
- **사용자 친화적 UI**: 터미널 기반의 컬러 UI, 페이지네이션 지원, 자동 정렬.
- **강력한 오류 처리**: 자동 재접속(Backoff) 및 해외 데이터 필드 보정 레이어.

## 4. 사용 방법 (How to Use)

1. 터미널에서 `python trading/main.py` 실행.
2. 암호화 비밀번호 입력.
3. 대화형 메뉴를 통해 기능 수행:
   - `1`: 계좌 정보 조회 (Summary/US/KR 순환).
   - `2`: 주문 실행 (US/KR 토글).
   - `3`: 미체결 주문 관리.
   - `r`: RAOEO 자동 주문 전략 실행.
   - `p`: 통합 포트폴리오 현황 요약 및 CSV 내보내기.
   - `c/q`: 시스템 초기화 및 종료.

---
*각 모듈의 상세 구현 사항은 폴더 구조의 (md) 파일을 참조하십시오.*
