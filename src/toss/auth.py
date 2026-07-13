"""Compatibility module for the migrated Toss infrastructure adapter."""

import sys
from importlib import import_module

from core.constants import CONFIG_ROOT
from core.credentials import load_credentials
from infrastructure.toss.auth import configure_auth_configuration

configure_auth_configuration(
    config_root=CONFIG_ROOT,
    credentials_loader=load_credentials,
)
sys.modules[__name__] = import_module("infrastructure.toss.auth")
