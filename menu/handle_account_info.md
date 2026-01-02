# handle_account_info.md

이 모듈은 통합 계좌 정보를 조회하고 표시하는 대화형 엔진과 데이터 fetching 로직을 관리합니다. 기존 `account_helper.py`의 기능을 통합하여 계좌 관련 모든 데이터 처리를 담당합니다.

## Purpose (목적)
사용자가 국내 및 해외 자산, 포트폴리오를 편리하게 모니터링할 수 있는 인터페이스를 제공하며, 재사용 가능한 데이터 조회(Fetch) 로직을 포함합니다.

## Debugging (디버깅)

이 모듈은 `menu.menu.MENU_DEBUG` 플래그를 참조하여 상세 로깅을 수행합니다.
- **MENU_DEBUG = True**: API 응답 데이터 전문 및 개별 종목 매핑 결과(Mapped KR/US)를 `WebSocket_latest.log`에 기록합니다.

## Workflow (동작 프로세스)

1. **Load Request**: 메인 메뉴에서 계좌 조회 요청(1)을 수신합니다.
2. **Data Integration**: `fetch_account_data`를 통해 `fetch_domestic_balance`와 `fetch_overseas_balance`를 병렬 또는 순차적으로 호출하여 데이터를 집계합니다.
3. **Initial Render**: 가져온 데이터를 `print_account_info`에 전달하여 'Account Summary' 뷰를 기본으로 렌더링합니다.
4. **User Interaction**: 사용자로부터 키 입력을 대기합니다 (`msvcrt.getch`).
5. **View Toggle**: 'f'키 입력 시 Summary -> US List -> KR List 순으로 뷰 모드를 전환합니다.
6. **Pagination**: 리스트 뷰에서 'n'키 입력 시 다음 페이지의 종목 리스트를 표시합니다.
7. **Exit**: 'q'키 입력 시 UI 영역을 정리하고 메인 메뉴로 복귀합니다.

## Function (기능)



### print_account_info
제공된 데이터를 바탕으로 터미널 UI를 렌더링하고 사용자의 키 입력(뷰 전환, 페이지 이동)을 처리합니다.
#### input
- `data` (dict): `fetch_account_data`로부터 받은 데이터 객체.
#### output
- `None` (화면 출력 및 `msvcrt.getch()`를 통한 루프 제어)

### fetch_price
해외 종목의 실시간 현재가(장 중) 또는 기준가(장 종료 후)를 KIS API를 통해 조회합니다.
내부적으로 `trading_config.get_kis_exchange_code`를 사용하여 거래소 코드를 자동으로 찾아오므로, 호출 시 거래소 코드를 생략할 수 있습니다.
#### input
- `ticker` (str): 종목 티커.
- `exchange` (str, optional): 거래소 코드 (NAS, NYS, AMS). 생략 시 자동 매핑.
#### output
- `float`: 현재가 또는 기준가. 실패 시 `0.0`.

---

### handle_account_info
메인 메뉴에서 호출되는 컨트롤러 함수입니다. 초기 로딩 상태를 표시하고 데이터 조회 후 출력 함수를 실행합니다.
#### input
- `None`
#### output
- `None`
