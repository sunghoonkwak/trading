"""Deprecated compatibility exports for Telegram report formatting."""

from interfaces.telegram.report_formatter import (
    format_rebalancing_report,
    format_strategy_report,
)

__all__ = ["format_rebalancing_report", "format_strategy_report"]
