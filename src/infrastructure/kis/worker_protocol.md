# KIS Worker Protocol (`infrastructure.kis.worker_protocol`)

KIS worker의 request/response dataclass와 KIS 전용 request/response queue를
소유합니다. KIS worker와 그 호출자가 이 protocol을 직접 사용합니다.

이 protocol은 worker의 인증 요청 상관관계와 queue 동작만 정의합니다.
