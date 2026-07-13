# KIS WebSocket Parser (`src/infrastructure/kis/ws_parser.py`)

이 모듈은 KIS 이벤트 어댑터가 이름이 붙은 WebSocket record를 로그에 남길 때
민감 필드를 마스킹하는 인프라 helper입니다. 기존 `src/kis/ws_parser.py`는 이
모듈을 가리키는 호환 export입니다.

## Purpose (목적)

KIS 실시간 API는 샘플 컬럼 정의와 실제 WebSocket payload의 필드 개수가 일시적으로
어긋날 수 있습니다. 특히 주문 체결 통보처럼 운영상 중요한 메시지에서 컬럼 수가
맞지 않으면 `pandas.DataFrame(..., columns=...)` 생성이 실패하고 WebSocket 루프가
재접속으로 빠질 수 있습니다.

vendor tree에 새 파일을 추가하지 않기 위해, `kis_auth.py`가 반드시 실행해야 하는
레코드 폭 보정·schema-drift rate-limit·알림 문구 생성은 그 파일 안의 최소 호환
패치로 유지합니다. 이 인프라 helper는 vendor 밖에서 필요한 dict 마스킹만 담당합니다.

일부 TR은 KIS가 더 넓은 payload를 보내지만 애플리케이션이 앞쪽 핵심 필드만 사용하는
호환 처리 경로가 있습니다. 예를 들어 해외 호가 `HDFSASP0`는 10단 호가 전체 payload를
받아도 1호가 필드만 사용하므로, 이 의도된 truncation은 warning으로 남기지 않습니다.

## Key Functions (주요 함수)

### `mask_dict_for_log(data)`

`infrastructure.kis.event_handler`의 주문 통보 `FULL DUMP`처럼 이름이 붙은 dict 형태의 record에서
동일한 민감 필드를 `********`로 치환합니다.

## Operational Notes (운영 메모)

`kis_auth.py`의 WebSocket 파서는 mismatch 발생 시 다음 형태의 warning을 남깁니다.

```text
Normalized WebSocket record for H0GSCNI0: padded 1 missing field(s): ['CNTG_UNPR12'] (raw=24, columns=25, record=[...])
```

이 로그의 `raw`는 수신 필드 수, `columns`는 로컬 컬럼 정의 수입니다. `record`는 필드
위치를 보존한 배열이므로 KIS API 변경 후 어느 위치가 빠지거나 추가됐는지 확인하는 데
사용합니다.

예상 밖 drift는 Telegram으로도 요약 알림을 보냅니다. 알림에는 `tr_id`, 보정 내용,
정렬 후 `fields`/`columns` 개수만 포함되며 record 값은 포함하지 않습니다.
