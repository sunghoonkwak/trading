"""Compatibility module for the migrated Toss infrastructure adapter."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module("infrastructure.toss.get_order")
