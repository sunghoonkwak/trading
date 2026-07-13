# -*- coding: utf-8 -*-
"""File lock adapter that prevents concurrent trading runtime instances."""
import fcntl
import logging
import os

LOCK_FILE = ".app.lock"
_lock_file_handle = None


def acquire_lock(base_dir: str) -> bool:
    """Acquire the non-blocking process lock for ``base_dir``."""
    lock_path = os.path.join(base_dir, LOCK_FILE)
    lock_file = None

    try:
        lock_file = open(lock_path, "a")
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

        global _lock_file_handle
        _lock_file_handle = lock_file
        return True
    except BlockingIOError:
        if lock_file is not None:
            lock_file.close()
        return False
    except Exception as error:
        logging.error("Error acquiring lock: %s", error)
        return False
