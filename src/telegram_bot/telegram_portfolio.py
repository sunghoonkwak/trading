"""Deprecated compatibility exports for the Telegram portfolio interface."""

from interfaces.telegram.portfolio import (
    get_portfolio_commands_desc,
    register_portfolio_handlers,
)

__all__ = ["get_portfolio_commands_desc", "register_portfolio_handlers"]
