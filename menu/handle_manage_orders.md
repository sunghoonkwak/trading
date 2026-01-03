# Manage Orders (`handle_manage_orders.py`)

이 모듈은 미체결 주문의 조회, 정정 및 취소 기능을 담당하며, 정해진 6단계 프로세스에 따라 동작합니다.

## Purpose (목적)
사용자가 현재 시장에 나간 미체결 주문들을 확인하고, 가격 정정이나 취소 작업을 수행할 수 있는 통합 관리 인터페이스를 제공하는 것입니다.

## Debugging (디버깅)

이 모듈은 `menu.menu.MENU_DEBUG` 플래그를 참조하여 상세 로깅을 수행합니다.
- **MENU_DEBUG = True**: 미체결 내역 조회 결과와 취소/정정 실행 시 사용된 파라미터를 `WebSocket_latest.log`에 상세히 기록합니다.

## Workflow (동작 프로세스)

1. **Open Order Fetching**: `fetch_open_orders`를 호출하여 국내/해외 미체결 내역을 가져옵니다.
2. **Order Selection**: 사용자로부터 관리할 주문의 번호(Index)를 입력받습니다.
3. **Action Selection**: 정정(Correct) 또는 취소(Cancel) 중 수행할 액션을 선택합니다.
4. **Price Input**: 정정 요청인 경우, 새로운 가격을 입력받습니다.
5. **Execution**: `execute_manage_action`을 호출하여 KIS API에 명령을 전송합니다.
6. **Print Result**: `print_execution_result`를 통해 처리 결과를 화면에 출력합니다.

## Function (기능)

### fetch_open_orders
해외(US) 및 국내(KR) 시장의 미체결 내역을 순차적으로 조회합니다.
#### input
- `None` (내부적으로 `kis_auth` 세션 사용)
#### output
- `tuple[DataFrame, int, int]`: (결과 데이터프레임, 미국 주문 수량, 국내 주문 수량).

### print_open_orders_list
미체결 주문 내역을 터미널에 출력하기 좋게 포매팅합니다.
#### input
- `df` (DataFrame): 미체결 내역 데이터.
- `market` (str): 시장 코드.
#### output
- `list[str]`: UI에 출력할 문자열 리스트.

### execute_manage_action
선택한 액션(정정/취소)을 실제 API로 실행합니다.
#### input
- `market` (str): 시장 코드.
- `action_type` (str): '1'(정정) 또는 '2'(취소).
- `order_data` (Series/dict): 원본 주문 데이터.
- `new_price` (str, optional): 정정 시 새로운 가격.
#### output
- `DataFrame`: API 응답 결과 데이터프레임.

### print_execution_result
API 응답 결과를 분석하여 성공/실패 여부와 메시지를 UI에 표시합니다.
#### input
- `df_res` (DataFrame): API 실행 결과 데이터.
#### output
- `None` (결과를 `show_in_result_area`를 통해 즉시 출력)

### sync_open_orders
둘러보기(Manage Orders) 진입 시 또는 실시간 이벤트 수신 시 호출되어 서버의 미체결 내역을 메인 UI의 하단 목록에 동기화합니다. 기존 목록을 초기화한 후 최신 데이터만 반영합니다.
#### input
- `None`.
#### output
- `None`. (로그: `[ORD] updated! Orders US/KR : ...`)

### SyncManager / request_sync
주문 동기화 요청을 관리하는 클래스와 헬퍼 함수입니다. 1초의 디바운스(Debounce) 시간을 적용하여, 수많은 WebSocket 이벤트가 한꺼번에 발생하더라도 서버 API 호출은 한 번만 수행되도록 최적화하며 레이스 컨디션을 방지합니다.
#### input
- `None`.
#### output
- `None`.

### handle_manage_orders
위에 정의된 6단계 흐름을 조율하는 메인 컨트롤러 함수입니다.
#### input
- `None` (메뉴 로직에 의해 정기 호출)
#### output
- `None`
