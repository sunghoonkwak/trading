# KIS WebSocket Parser (`src/kis/ws_parser.py`)

KIS WebSocket 실시간 메시지를 `DataFrame`으로 만들기 전에 레코드 폭을 보정하고,
진단 로그에서 민감 필드를 마스킹하는 작은 helper 모듈입니다.

## Purpose (목적)

KIS 실시간 API는 샘플 컬럼 정의와 실제 WebSocket payload의 필드 개수가 일시적으로
어긋날 수 있습니다. 특히 주문 체결 통보처럼 운영상 중요한 메시지에서 컬럼 수가
맞지 않으면 `pandas.DataFrame(..., columns=...)` 생성이 실패하고 WebSocket 루프가
재접속으로 빠질 수 있습니다.

이 모듈은 그런 스키마 drift를 WebSocket 장애로 확대하지 않도록 다음을 담당합니다.

1. **레코드 폭 보정**: 실제 필드가 부족하면 빈 문자열로 padding하고, 초과하면 컬럼
   정의 길이에 맞춰 truncation합니다.
2. **진단 로그 지원**: mismatch 발생 시 원문 필드 위치를 확인할 수 있도록 record
   배열을 로그에 남기되, 계좌/고객/주문 식별자는 마스킹합니다.
3. **운영 알림 지원**: 예상 밖 스키마 drift는 같은 `tr_id` 기준 1시간에 한 번만
   Telegram 알림을 보낼 수 있도록 알림 문구와 rate-limit 판단을 제공합니다.

일부 TR은 KIS가 더 넓은 payload를 보내지만 애플리케이션이 앞쪽 핵심 필드만 사용하는
호환 처리 경로가 있습니다. 예를 들어 해외 호가 `HDFSASP0`는 10단 호가 전체 payload를
받아도 1호가 필드만 사용하므로, 이 의도된 truncation은 warning으로 남기지 않습니다.

## Key Functions (주요 함수)

### `normalize_record(record, columns)`

수신 record의 길이를 컬럼 정의와 맞춥니다.

- 필드 수가 같으면 그대로 반환합니다.
- 필드 수가 부족하면 누락 컬럼 수만큼 `""`를 뒤에 채웁니다.
- 필드 수가 많으면 컬럼 정의 길이까지만 사용합니다.
- 보정이 발생한 경우 로그에 사용할 설명 문자열을 함께 반환합니다.

### `mask_record_for_log(record, columns)`

운영 로그에 남길 record 배열에서 민감 필드를 `********`로 치환합니다.

현재 마스킹 대상:

- `CUST_ID`
- `ACNT_NO`
- `ACNT_NO2`
- `ODER_NO`
- `OODER_NO`
- `ACNT_NAME`

### `mask_dict_for_log(data)`

`event_handler.py`의 주문 통보 `FULL DUMP`처럼 이름이 붙은 dict 형태의 record에서
동일한 민감 필드를 `********`로 치환합니다.

### `should_log_normalization(note, expected_truncation)`

레코드 보정이 운영자가 확인해야 하는 스키마 drift인지 판단합니다.

- 의도된 호환 truncation은 로그를 남기지 않습니다.
- 누락 필드 padding은 실제 스키마 mismatch 후보이므로 로그를 남깁니다.

### `should_send_schema_drift_alert(sent_at, tr_id, now, interval_seconds=3600)`

동일 `tr_id`에 대한 schema drift Telegram 알림을 제한합니다. 기본적으로 첫 발생 후
1시간 동안 같은 `tr_id`의 반복 알림은 보내지 않습니다.

### `build_schema_drift_alert(tr_id, note, field_count, column_count)`

Telegram에 보낼 요약 알림 문구를 만듭니다. 원문 record 값은 포함하지 않고, 상세
마스킹 record는 파일 로그에서만 확인합니다.

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
