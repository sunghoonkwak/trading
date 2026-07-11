"""Compatibility module for the Toss infrastructure trading adapter."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module("infrastructure.toss.toss_broker")
