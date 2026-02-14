# Data Service (`src/data/data_service.py`)

애플리케이션 전반에서 사용되는 포트폴리오 및 시장 데이터를 관리하는 중앙 서비스 모듈입니다.
데이터 조회(I/O), 캐싱, 그리고 복잡한 데이터 변환 로직을 분리하여 제공합니다.

# Core Logic (핵심 로직)

1. **캐시 관리 (`PortfolioCacheManager`)**: 5분(300초) 동안 유효한 메모리 캐시를 관리하여 불필요한 API 호출을 줄입니다.
2. **데이터 처리 (`PortfolioProcessor`)**: 
   - KIS API에서 받은 원시 데이터를 병합(Merge)하고 보유 종목별 평단가, 수익률 등을 계산합니다.
   - 현금(USD/KRW)을 가상의 종목으로 취급하여 비중 계산에 포함시킵니다.
   - 포트폴리오 통계(국가별 비중, 총 평가액 등)를 산출합니다.
3. **스코프 필터링**: 전체 계좌, KIS 계좌, 패시브 계좌 등 목적에 맞게 데이터를 필터링하여 제공합니다.
4. **리밸런싱 계산**: 현재 비중과 목표 비중을 비교하여 필요한 매매 수량을 산출합니다.

# Key Functions (주요 함수)

## `get_portfolio_data`
캐시를 확인하거나 KIS 스레드에 요청하여 최신 포트폴리오 데이터를 가져옵니다.

- **입력 (Input)**:
  - `force_refresh` (bool): 캐시 무시 여부.
  - `scope` (str): 필터링 범위 ("all", "kis", "passive").
- **출력 (Output)**: `dict` (병합된 보유 현황, 통계, 비중 정보 등).

## `get_weight_diffs`
현재 비중과 목표 비중의 차이를 계산하여 리밸런싱 정보를 제공합니다.

- **출력 (Output)**: `Tuple[List[Dict], float, Dict]` (차이 목록, 총 가치, 현금 정보).

# Configuration (`portfolio_weights.json`)
리밸런싱을 위한 목표 비중 설정 파일을 참조합니다.

# Usage Example (사용 예시)

```python
from data.data_service import get_portfolio_data

# 전체 포트폴리오 데이터 조회
data = get_portfolio_data(scope="all")
print(f"Total Value: ${data['total_value_usd']:.2f}")

# KIS 계좌 전용 데이터 조회
kis_data = get_portfolio_data(scope="kis")
```
