# Portfolio Scope (`src/data/portfolio_scope.py`)

이 모듈은 포트폴리오 조회 scope 문자열 계약을 한 곳에서 관리합니다.

## Responsibilities

- `all`, `kis`, `toss` scope 상수를 제공합니다.
- `normalize_portfolio_scope`로 입력 scope를 소문자 정규화하고 허용값을
  검증합니다.
- `data_service.py`, `portfolio_integration.py` 같은 호출부가 동일한
  scope 계약을 공유하게 합니다.

## Scope Semantics

- `all`: 전체 포트폴리오 확인용입니다. KIS, GSheet, Toss를 통합 조회하며
  Toss API 실패 시 GSheet의 `토스` 계정 fallback을 허용합니다.
- `kis`: 전략 실행 또는 KIS 계좌 전용 조회용입니다. KIS API 데이터만
  사용합니다.
- `toss`: 전략 실행 또는 Toss 계좌 전용 조회용입니다. Toss API 데이터와
  Toss 환율만 사용하며, 주문 판단에 GSheet fallback을 사용하지 않습니다.

## Boundary

이 모듈은 문자열 상수와 validation만 담당합니다. 실제 source fetch,
fallback 정책 실행, 포트폴리오 병합은 `portfolio_integration.py`가
담당합니다.
