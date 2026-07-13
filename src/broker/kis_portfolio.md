# KIS Portfolio Source (`src/broker/kis_portfolio.py`)

이 모듈은 infrastructure KIS 포트폴리오 어댑터의 임시 호환 export입니다.

## Responsibilities

- `KisPortfolioSourceAdapter`, `fetch_kis_portfolio()`,
  `get_integrated_portfolio()`를 기존 외부 호출자에 전달합니다.
- 구현과 KIS API 의존성은 `infrastructure.portfolio.kis_source`에 있습니다.
- 런타임 환경변수 `KIS_ENABLE_REST_API=false`이면 KIS REST 잔고/매수가능
  조회를 인증 전에 차단하고 빈 source와 disabled metadata를 반환합니다.
- `get_integrated_portfolio(scope="all")`를 제공합니다.
- `get_integrated_portfolio`는
  `infrastructure.portfolio.integration.get_integrated_portfolio`로 lazy 위임합니다.
- KIS 국내주식 잔고조회는 기본 비활성화되어 있습니다. 국내 계좌를
  다시 포함하려면 런타임 환경변수 `KIS_ENABLE_DOMESTIC=true`를 설정합니다.
- 해외 현재잔고 응답에서 환율을 찾지 못하면 `inquire_psamount`의 `exrt`를
  fallback 환율로 사용합니다. 보유 종목이 0개여도 KRW 현금/자산 변환에
  필요한 환율을 유지하기 위함입니다.

## Import Boundary

`infrastructure.portfolio.integration`은
`infrastructure.portfolio.kis_source`에서 표준 source 데이터를 읽어
병합합니다. KIS raw API 조회와 KIS raw 응답 필드 처리는 infrastructure에
두고, 공식 KIS endpoint wrapper는 `src/infrastructure/kis/kis_api/` 경계를
그대로 사용합니다. 전체 자산 병합 정책도 infrastructure adapter에 있습니다.
