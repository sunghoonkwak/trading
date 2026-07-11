"""Compatibility package for the relocated KIS vendor distribution.

New application-owned code imports ``infrastructure.kis.kis_api`` directly.
This module retains the historical ``kis.kis_api`` path for scripts and
third-party KIS sample imports during the migration window.
"""

import sys
from importlib import import_module

sys.modules[__name__] = import_module("infrastructure.kis.kis_api")
