# KIS Portfolio Source (`src/broker/kis_portfolio.py`)

이 모듈은 앱 소유 영역에서 KIS 포트폴리오 조회 경계를 제공합니다.

## Responsibilities

- `fetch_kis_portfolio()`로 KIS API 데이터를 조회하고 표준 source 포맷으로
  변환합니다.
- KIS 조회 실패 시 빈 source와 raw metadata를 반환해 data 계층이 병합
  정책을 계속 적용할 수 있게 합니다.
- `get_integrated_portfolio(kis_only=False)`를 제공합니다.
- `get_integrated_portfolio`는 기존 호출부 호환을 위해
  `data.portfolio_integration.get_integrated_portfolio`로 lazy 위임합니다.

## Import Boundary

`broker.portfolio`는 이 모듈을 lazy-load한 뒤 표준 source 데이터를
data 계층에 제공합니다. KIS raw API 조회와 KIS raw 응답 필드 처리는
broker 계층에 두고, 공식 KIS endpoint wrapper는 `src/kis/kis_api/`
경계를 그대로 사용합니다. 전체 자산 병합 정책은 data 계층에 둡니다.
