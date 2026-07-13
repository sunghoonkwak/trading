import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


def test_acquire_lock_returns_false_and_closes_file_when_locked(monkeypatch, tmp_path):
    from infrastructure import lock_manager

    class LockFile:
        closed = False

        def fileno(self):
            return 1

        def close(self):
            self.closed = True

    lock_file = LockFile()
    monkeypatch.setattr("builtins.open", lambda *_args, **_kwargs: lock_file)
    monkeypatch.setattr(
        lock_manager.fcntl,
        "flock",
        lambda *_args: (_ for _ in ()).throw(BlockingIOError()),
    )

    assert lock_manager.acquire_lock(str(tmp_path)) is False
    assert lock_file.closed is True
