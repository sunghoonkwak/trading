import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from state import system_state


def test_kis_ready_reflects_worker_and_auth_state():
    try:
        system_state.update_kis_state(
            thread_status=system_state.ThreadStatus.NOT_STARTED,
            auth_status=system_state.AuthStatus.NOT_AUTHENTICATED,
        )

        assert system_state.is_kis_ready() is False

        system_state.update_kis_state(
            thread_status=system_state.ThreadStatus.RUNNING,
            auth_status=system_state.AuthStatus.AUTHENTICATED,
        )

        assert system_state.is_kis_ready() is True
    finally:
        system_state.update_kis_state(
            thread_status=system_state.ThreadStatus.NOT_STARTED,
            auth_status=system_state.AuthStatus.NOT_AUTHENTICATED,
        )
