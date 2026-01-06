# Place Order (`handle_place_order.py`)

이 모듈은 주식 매수 및 매도 주문을 넣는 대화형 인터페이스와 데이터 조회 로직을 처리합니다.

## Purpose (목적)
다양한 시장(KR/US)에 대해 정교한 주문 입력(가격, 수량)을 지원하고, 실시간 시세 및 잔고 데이터를 조회하여 주문 가능 수량을 가이드하는 역할을 합니다.

## Debugging (디버깅)

이 모듈은 `menu.menu.MENU_DEBUG` 플래그를 참조하여 상세 로깅을 수행합니다.
- **MENU_DEBUG = True**: 주문 실행 시 티커, 방향, 수량, 가격 등의 파라미터와 KIS 서버의 실제 응답 데이터를 `WebSocket_latest.log`에 상세히 기록합니다.

## Workflow (동작 프로세스)

1. **Market Selection**: 기본 US 시장으로 시작하며, 엔터키를 통해 KR/US 시장을 토글할 수 있습니다.
2. **Side Selection**: 1(매수) 또는 2(매도)를 선택하여 거래 방향을 결정합니다.
3. **Stock Selection**: 설정파일에 등록된 관심 종목 리스트에서 번호를 선택하거나, 99번을 통해 티커를 직접 입력합니다.
4. **Price Input**: 주문 가격을 직접 입력하거나, 엔터를 눌러 최신 시세를 확인할 수 있습니다. 직접 입력하지 않은 경우 시세를 화면에 표시하고 해당 가격의 적용 여부를 다시 한번 확인받습니다.
5. **Quantity Input**: 주문 수량을 입력합니다. 이때 가용 잔고를 기반으로 최대 가능 수량이 안내됩니다.
6. **Order Confirmation**: 입력된 상세 내역을 요약하여 보여주고 사용자의 최종 승인(`y/n`)을 받습니다.
7. **Execution & Result**: `execute_place_order`를 통해 실제 API를 호출하고 성공/실패 결과를 화면에 표시합니다.

## Function (기능)

### fetch_balances
`data_service.get_portfolio_data`를 통해 계좌의 국내(KRW) 및 해외(USD) 주문 가능 잔고를 조회합니다.
(자세한 데이터 구조는 [`data/data_service.md`](../data/data_service.md) 참조)
#### input
- `None`
#### output
- `tuple[int, float]`: (KRW 잔고, USD 잔고).

### fetch_stock_price
`trading_state`에 저장된 특정 종목의 최신 시세(현재가 또는 매도호가)를 가져옵니다.
#### input
- `pdno` (str): 종목 코드 (Ticker).
#### output
- `float`: 현재 시세 또는 매도호가 값.

### execute_place_order
실제 KIS API 모듈을 호출하여 시장에 주문을 전송합니다.
#### input
- `target_market` (str): 'KR' 또는 'US'.
- `ord_dv` (str): 'buy' 또는 'sell'.
- `pdno` (str): 종목 코드.
- `qty` (str/int): 주문 수량.
- `price_input` (str): 사용자 입력 가격 (0이면 시장가 등).
- `price_val` (float): 계산된 실제 주문 가격.
#### output
- `DataFrame`: KIS API 호출 결과 데이터프레임.

### handle_place_order
메인 메뉴 컨트롤러입니다. 시장 선택, 종목 선택(관심종목 리스트), 주문 상세 입력 및 실행의 전체 워크플로우를 관리합니다.
#### input
- `None`
#### output
- `None`
