# -*- coding: utf-8 -*-
"""
I/O Utilities Module

Handles platform-specific keyboard input.
"""
import sys

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import msvcrt
    def getch() -> bytes:
        return msvcrt.getch()
    def getch_str() -> str:
        return msvcrt.getch().decode('utf-8', errors='ignore')
else:
    import tty
    import termios
    def getch() -> bytes:
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return sys.stdin.read(1).encode('utf-8')
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    def getch_str() -> str:
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
