# KIS Worker Protocol (`infrastructure.kis.worker_protocol`)

KIS worker의 request/response dataclass와 KIS 전용 request/response queue를
소유합니다. `core.thread_comm`은 기존 호출자의 import 호환성을 위해 이
객체들을 re-export할 뿐, 별도 queue를 만들지 않습니다.

이 protocol은 worker의 인증 요청 상관관계와 queue 동작만 정의합니다.
Telegram, status, WebSocket data queue는 `core.thread_comm`에 남아 있습니다.
