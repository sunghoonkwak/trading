# -*- coding: utf-8 -*-
"""
Logging Management Module

Handles system-wide logging configuration, file rotation, and archiving.
"""
import os
import re
import sys
import shutil
import logging
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from typing import List

class LogManager:
    """Manages the lifecycle and configuration of system logs."""

    @classmethod
    def setup(cls, base_dir: str, log_name: str = "trading_system.log"):
        """Configures the root logger with rotation and custom namers."""
        # 1. Resolve Paths
        logs_dir = os.path.join(base_dir, "logs") if os.path.basename(base_dir) != "src" else os.path.join(os.path.dirname(base_dir), "logs")
        log_file = os.path.join(os.path.dirname(logs_dir), log_name)

        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)

        base_name = os.path.splitext(log_name)[0]

        # 2. Archive existing log if fresh session
        rotation_msgs = cls._archive_existing_log(log_file, logs_dir, base_name)

        # 3. Reset Root Logger
        root_logger = logging.getLogger()
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)

        # 4. Configure Timed Handler (Daily rotation at midnight)
        file_handler = TimedRotatingFileHandler(log_file, when='midnight', interval=1, encoding='utf-8')
        file_handler.suffix = "%y_%m_%d_%H_%M_%S"
        file_handler.namer = lambda name: cls._log_namer(name, logs_dir, base_name)
        file_handler.rotator = cls._log_rotator

        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        file_handler.setFormatter(formatter)

        # Console output (stream)
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)

        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(stream_handler)

        # Remove stream handler so future logs primarily go to file
        root_logger.removeHandler(stream_handler)

        # 5. Suppress noisy third-party logs
        for lib in ["httpx", "httpcore", "telegram", "apscheduler", "websockets", "asyncio"]:
            logging.getLogger(lib).setLevel(logging.WARNING)

        # 6. Log Initial Messages
        for msg in rotation_msgs:
            logging.info(msg)
        logging.info(f"[LogManager] Logging initialized. Active log: {os.path.basename(log_file)}")

        return log_file

    @staticmethod
    def _archive_existing_log(log_file: str, logs_dir: str, base_name: str = "trading_system") -> List[str]:
        """Moves current log to archive with timestamp."""
        msgs = []
        if not os.path.exists(log_file):
            msgs.append("[LogRotation] Fresh session. No existing log file found.")
            return msgs

        old_ts = ""
        try:
            with open(log_file, "r", encoding="utf-8-sig") as f:
                for _ in range(20):
                    line = f.readline()
                    if not line: break
                    match = re.search(r"(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})", line)
                    if match:
                        y, m, d, hh, mm, ss = match.groups()
                        old_ts = f"{y[2:]}_{m}_{d}_{hh}_{mm}_{ss}"
                        break
        except: pass

        if not old_ts:
            try:
                mtime = os.path.getmtime(log_file)
                old_ts = datetime.fromtimestamp(mtime).strftime("%y_%m_%d_%H_%M_%S")
            except:
                old_ts = datetime.now().strftime("%y_%m_%d_%H_%M_%S")

        archive_name = os.path.join(logs_dir, f"{base_name}_{old_ts}.log")
        if os.path.exists(archive_name):
            archive_name = archive_name.replace(".log", f"_{int(datetime.now().timestamp())}.log")

        try:
            shutil.move(log_file, archive_name)
            msgs.append(f"[LogRotation] Archived old log: {os.path.basename(archive_name)}")
        except Exception as e:
            msgs.append(f"[LogRotation] Archive error: {e}")
        return msgs

    @staticmethod
    def _log_namer(default_name: str, logs_dir: str, base_name: str = "trading_system") -> str:
        """Custom namer for TimedRotatingFileHandler."""
        base = os.path.basename(default_name)
        parts = base.split('.')
        if len(parts) >= 3:
            return os.path.join(logs_dir, f"{base_name}_{parts[-1]}.log")
        return os.path.join(logs_dir, base)

    @staticmethod
    def _log_rotator(source: str, dest: str):
        """Custom rotator for TimedRotatingFileHandler."""
        if os.path.exists(source):
            try: shutil.move(source, dest)
            except Exception as e: print(f"[LogRotation] Runtime error: {e}")
