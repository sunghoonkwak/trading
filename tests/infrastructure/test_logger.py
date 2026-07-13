import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


def test_log_manager_archives_existing_log_with_its_timestamp(tmp_path):
    from infrastructure.logger import LogManager

    log_file = tmp_path / "trading_system.log"
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    log_file.write_text(
        "2026-07-13 12:34:56 [INFO] Existing session\n",
        encoding="utf-8",
    )

    messages = LogManager._archive_existing_log(
        str(log_file),
        str(logs_dir),
    )

    archived_log = logs_dir / "trading_system_26_07_13_12_34_56.log"
    assert not log_file.exists()
    assert archived_log.read_text(encoding="utf-8") == (
        "2026-07-13 12:34:56 [INFO] Existing session\n"
    )
    assert messages == [
        "[LogRotation] Archived old log: trading_system_26_07_13_12_34_56.log"
    ]


def test_log_manager_formats_rotated_log_names():
    from infrastructure.logger import LogManager

    assert LogManager._log_namer(
        "trading_system.log.26_07_13_12_34_56",
        "/tmp/logs",
    ) == "/tmp/logs/trading_system_26_07_13_12_34_56.log"
