# KIS Portfolio Facade (`src/broker/kis_portfolio.py`)

이 모듈은 앱 소유 영역에서 KIS 포트폴리오 조회 경계를 제공합니다.

## Responsibilities

- `get_integrated_portfolio(kis_only=False)`를 제공합니다.
- 현재 구현은 기존 `kis.portfolio_manager.PortfolioManager`로 lazy 위임합니다.
- `RESTClient`가 포트폴리오 병합 정책 클래스를 직접 보지 않도록 하는
  전환 seam입니다.

## Import Boundary

`PortfolioManager`는 함수 호출 시점에 lazy-load합니다. 클래스 본체 이동 전까지
기존 테스트와 내부 메서드 검증은 `kis.portfolio_manager`에 남겨둡니다.
