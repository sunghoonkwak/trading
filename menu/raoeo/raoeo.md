# raoeo.md

이 모듈은 라오어 무한 매수법에 필요한 매매 계산 및 주문을 자동으로 처리하는 모듈입니다.

## Purpose (목적)

라오어 무한 매수법에 필요한 매매 계산 및 주문을 자동으로 처리하는 모듈입니다.

## Menu Options (메뉴 옵션)

| Key | Action |
|-----|--------|
| `1` | Calculate & Execute | 주문 계산 및 실행 |
| `2` | View History | 누적 히스토리 조회 (Pagination) |
| `q` | Quit | 이전 메뉴로 돌아가기 |

## Function (기능)

### load_config
raoeo.json 파일에서 설정을 로드합니다.
seed: 매매법에 사용할 초기 자금
target: 매매법에 사용할 종목
duration: 매매법에 사용할 기간
sell_profit: 매매법에 사용할 수익률
#### input
- `None`.
#### output
- `dict`: 설정 정보.

### calculate_order
당일에 매수/매도 주문해야하는 가격/수량을 계산합니다.
1. load_config를 통해서 설정 정보를 로드합니다.
2. fetch_overseas_balance를 통해서 현재 보유중인 target 주식의 평단가를 확인합니다.
3. 내 평단가 * 110%(평단가 + 10%)의 price로 보유한 주식 전체를 매도합니다.
4. 당일 사용가능한 자금(seed/duration)을 아래와 같은 비율로 매수계산합니다.
    - initial상태(보유주식이 없는상태): 금일 현재가 * 110%의 price로 당일 사용가능한 자금 전체를 LOC 매수합니다.
    - 보유상태:
        a. 1/2: 내 평단가 * (Sell Profit - 1%)의 price로 LOC 매수  ## 자전거래 방지를 위해 매도 수익률보다 1% 낮게 설정 (자동 계산)
        b. 1/2: 내 평단가의 price로 LOC 매수                       ## 내 평단가보다 낮을경우 매수하여 평단가를 낮추기 위해
5. 계산된 매수/매도 주문을 dict로 반환합니다.
#### input
- `None`.
#### output
- `dict`: 당일 매수/매도 주문해야하는 가격/수량.

### view_history
`raoeo_history.json`에 저장된 과거 기록을 테이블 형식으로 조회합니다. 5개 항목씩 페이징 처리가 되어 있으며, `f`키로 다음 페이지, `g`키로 첫 페이지 이동이 가능합니다.

### update_history
주문 실행 성공 시 당일의 전략 상태(현재가, 평단가, 주문 내역 등)를 히스토리에 자동으로 저장합니다.
#### input
- `dict`: 당일 주문 및 전략 데이터.
#### output
- `None`.

### raoeo_menu
라오어 전략 메뉴의 메인 컨트롤러입니다. 루프 내부에서 `render_ui`를 호출하여 메인 화면의 실시간 주문/알림 영역이 유지되도록 합니다.