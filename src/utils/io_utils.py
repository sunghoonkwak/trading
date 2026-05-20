# -*- coding: utf-8 -*-
"""
I/O Utilities Module

Handles Linux terminal keyboard input.
"""
import sys
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
