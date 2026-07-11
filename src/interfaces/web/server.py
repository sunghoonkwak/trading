"""Temporary web adapter facade during the core-web migration."""

from core.web_server import set_portfolio_reader, start_web_server

__all__ = ["set_portfolio_reader", "start_web_server"]
