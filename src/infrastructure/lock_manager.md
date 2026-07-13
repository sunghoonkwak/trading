# Lock Manager (`src/infrastructure/lock_manager.py`)

애플리케이션의 단일 인스턴스 실행을 보장하는 파일 기반 infrastructure adapter입니다.

`acquire_lock(base_dir)`는 `.app.lock`에 non-blocking exclusive lock을 시도합니다.
성공하면 파일 핸들을 프로세스 수명 동안 유지하고, 이미 잠겨 있거나 오류가
발생하면 `False`를 반환합니다. `main.py`는 이 실패를 fail-closed startup으로
처리합니다.
