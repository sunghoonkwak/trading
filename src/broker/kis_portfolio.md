# KIS Portfolio Facade (`src/broker/kis_portfolio.py`)

이 모듈은 앱 소유 영역에서 KIS 포트폴리오 조회 경계를 제공합니다.

## Responsibilities

- `get_integrated_portfolio(kis_only=False)`를 제공합니다.
- 현재 구현은 `data.portfolio_integration.get_integrated_portfolio`로
  lazy 위임합니다.
- `RESTClient`가 포트폴리오 병합 정책 클래스를 직접 보지 않도록 하는
  전환 seam입니다.

## Import Boundary

통합 모듈은 함수 호출 시점에 lazy-load합니다. `kis.portfolio_manager`는
한투 원천 조회와 표준 포맷 변환만 담당하고, 전체 자산 병합 정책은
data 계층에 둡니다.
