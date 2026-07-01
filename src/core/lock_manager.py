# -*- coding: utf-8 -*-
"""
Lock Manager using fcntl

Ensures only one instance of the application runs at a time by acquiring
an exclusive lock on a file.
"""
import os
import fcntl
import logging

LOCK_FILE = ".app.lock"
_lock_file_handle = None


def acquire_lock(base_dir: str) -> bool:
    """
    Attempts to acquire an exclusive lock on .app.lock file.

    Args:
        base_dir: The root directory where .app.lock will be created.

    Returns:
        bool: True if lock acquired, False if another instance is running.
    """
    lock_path = os.path.join(base_dir, LOCK_FILE)
    lock_file = None

    try:
        lock_file = open(lock_path, 'a')
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

        global _lock_file_handle
        _lock_file_handle = lock_file
        return True

    except BlockingIOError:
        if lock_file is not None:
            lock_file.close()
        return False
    except Exception as e:
        logging.error(f"Error acquiring lock: {e}")
        return False
