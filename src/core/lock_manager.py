# -*- coding: utf-8 -*-
"""
Lock Manager using fcntl

Ensures only one instance of the application runs at a time by acquiring
an exclusive lock on a file.
"""
import os
import sys
import fcntl
import logging

LOCK_FILE = ".app.lock"

def acquire_lock(base_dir: str) -> bool:
    """
    Attempts to acquire an exclusive lock on .app.lock file.

    Args:
        base_dir: The root directory where .app.lock will be created.

    Returns:
        bool: True if lock acquired, False if another instance is running.
    """
    lock_path = os.path.join(base_dir, LOCK_FILE)

    try:
        # Open the file in append mode. We don't need to read/write content, just lock it.
        # We perform the open first.
        lock_file = open(lock_path, 'a')

        # Try to acquire an exclusive lock (LOCK_EX) without blocking (LOCK_NB).
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

        # If successful, we must keep the file open for the duration of the program.
        # We can store the file handle in a global or module-level variable to prevent garbage collection closing it.
        # Here we just return True, relying on the fact that if this module is imported,
        # the file object won't be closed unless we explicitly do so or the program exits.
        # To be safe, let's attach it to the function attribute or a global variable.
        global _lock_file_handle
        _lock_file_handle = lock_file

        return True

    except BlockingIOError:
        # This error is raised if the file is already locked.
        return False
    except Exception as e:
        logging.error(f"Error acquiring lock: {e}")
        # If we can't create/lock the file for other reasons, we should probably warn but proceed?
        # Or fail safe. Let's return False to be safe if we can't determine status.
        return False

# Keep a reference to prevent GC
_lock_file_handle = None
