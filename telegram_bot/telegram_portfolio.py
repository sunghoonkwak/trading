# -*- coding: utf-8 -*-
"""
Telegram Portfolio Module

This module handles portfolio specific Telegram commands.
"""
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from portfolio import get_portfolio, calc_weight_diffs

def format_portfolio_summary(data: dict) -> str:
    """Format portfolio summary for Telegram message."""
    if data.get("error"):
        return f"⚠️ *Error:* {data['error']}"

    stats = data.get("stats", {})
    total_usd = data.get("total_value_usd", 0)
    rate = data.get("exchange_rate", 0)
    total_krw = total_usd * rate if rate > 0 else 0

    lines = [
        f"💰 *Portfolio Summary* (Rate: {rate:,.1f})",
        "",
        f"**Total**: **${total_usd/1000:,.1f}K** (₩{total_krw/1000000:,.1f}M)",
        f"**Cash**: **{stats.get('total_cash_usd', 0) / total_usd * 100 if total_usd > 0 else 0:.1f}%**",
        "",
        f"🇺🇸 **US Assets**: ${stats.get('us_stock_usd', 0) + stats.get('us_cash_usd', 0) / 1000:,.1f}K ({stats.get('us_pct', 0):.1f}%)",
        f"  Stock: ${stats.get('us_stock_usd', 0)/1000:,.1f}K | Cash: {stats.get('us_cash_ratio', 0):.1f}%",
        f"🇰🇷 **KR Assets**: ₩{(stats.get('kr_stock_krw', 0) + stats.get('kr_cash_krw', 0))/1000000:,.1f}M ({stats.get('kr_pct', 0):.1f}%)",
        f"  Stock: ₩{stats.get('kr_stock_krw', 0)/1000000:,.1f}M | Cash: {stats.get('kr_cash_ratio', 0):.1f}%"
    ]
    return "\n".join(lines)

def format_weight_diffs(data: dict) -> str:
    """Format weight differences for Telegram message."""
    if data.get("error"):
        return f"⚠️ *Error:* {data['error']}"

    merged_data = data.get("merged_data", {})
    current_weights = data.get("current_weights", {})
    targets = data.get("targets", {})
    total_usd = data.get("total_value_usd", 0)
    rate = data.get("exchange_rate", 0)

    diffs = calc_weight_diffs(merged_data, current_weights, targets, total_usd, rate)

    if not diffs:
        return "⚖️ *Portfolio Rebalancing*\n\nEverything is balanced!"

    sell_lines = []
    buy_lines = []

    for d in diffs:
        # Show top diffs or those > 0.5%
        if d['abs_diff'] < 0.005:
            continue

        ticker = d['ticker']
        msg = f"- **{ticker}**: {d['diff']*100:+.1f}% ({d['cur_w']*100:.1f}% -> {d['tgt_w']*100:.1f}%) | **Qty: {d['qty_diff']:+d}**"

        if d['diff'] < 0:
            sell_lines.append(msg)
        else:
            buy_lines.append(msg)

    lines = [f"⚖️ *Portfolio Rebalancing* (Total: ${total_usd/1000:,.1f}K)", ""]

    if sell_lines:
        lines.append("🔴 **SELL**")
        lines.extend(sell_lines)
        lines.append("")

    if buy_lines:
        lines.append("🟢 **BUY**")
        lines.extend(buy_lines)
        lines.append("")

    if not sell_lines and not buy_lines:
        lines.append("No significant differences found (>0.5%).")
    else:
        lines.append("_*Significant changes (>0.5%) only_")

    return "\n".join(lines)

async def cmd_portfolio_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command handler for /portfolio_summary."""
    from .telegram_bot import wrap_reply

    # Run silently to not interrupt main thread UI
    data = get_portfolio()
    msg = format_portfolio_summary(data)
    await wrap_reply(update, msg, parse_mode='Markdown')

async def cmd_portfolio_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command handler for /portfolio_weight."""
    from .telegram_bot import wrap_reply

    # Run silently
    data = get_portfolio()
    msg = format_weight_diffs(data)
    await wrap_reply(update, msg, parse_mode='Markdown')

def register_portfolio_handlers(app: Application):
    """Register Portfolio command handlers."""
    app.add_handler(CommandHandler("portfolio_summary", cmd_portfolio_summary))
    app.add_handler(CommandHandler("portfolio_weight", cmd_portfolio_weight))

def get_portfolio_commands_desc() -> str:
    """Return Portfolio command descriptions for init message."""
    return (
        "/portfolio\\_summary \\- Portfolio asset summary\n"
        "/portfolio\\_weight \\- Rebalancing suggestions"
    )
