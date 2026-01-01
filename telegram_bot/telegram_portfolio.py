# -*- coding: utf-8 -*-
"""
Telegram Portfolio Module

This module handles portfolio specific Telegram commands with ConversationHandler
for interactive ticker selection.
"""
import logging
import warnings
from telegram.warnings import PTBUserWarning
warnings.filterwarnings("ignore", category=PTBUserWarning)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
    ConversationHandler, CallbackQueryHandler, MessageHandler, TypeHandler, filters
)
import display
from .telegram_utils import wrap_reply, wrap_edit

from menu.portfolio.portfolio import get_portfolio, calc_weight_diffs

# Conversation states
SELECT_TICKER = 0


def format_portfolio_summary(data: dict) -> str:
    """Format portfolio summary for Telegram message."""
    if data.get("error"):
        return f"⚠️ <b>Error:</b> {data['error']}"

    stats = data.get("stats", {})
    total_usd = data.get("total_value_usd", 0)
    rate = data.get("exchange_rate", 0)
    total_krw = total_usd * rate if rate > 0 else 0

    lines = [
        f"💰 <b>Portfolio Summary</b> (Rate: {rate:,.1f})",
        "",
        f"<b>Total</b>: <b>${total_usd/1000:,.1f}K</b> (₩{total_krw/1000000:,.1f}M)",
        f"<b>Cash</b>: <b>{stats.get('total_cash_usd', 0) / total_usd * 100 if total_usd > 0 else 0:.1f}%</b>",
        "",
        f"🇺🇸 <b>US Assets</b>: ${stats.get('us_stock_usd', 0) + stats.get('us_cash_usd', 0) / 1000:,.1f}K ({stats.get('us_pct', 0):.1f}%)",
        f"  Stock: ${stats.get('us_stock_usd', 0)/1000:,.1f}K | Cash: {stats.get('us_cash_ratio', 0):.1f}%",
        f"🇰🇷 <b>KR Assets</b>: ₩{(stats.get('kr_stock_krw', 0) + stats.get('kr_cash_krw', 0))/1000000:,.1f}M ({stats.get('kr_pct', 0):.1f}%)",
        f"  Stock: ₩{stats.get('kr_stock_krw', 0)/1000000:,.1f}M | Cash: {stats.get('kr_cash_ratio', 0):.1f}%",
        "",
        "📊 <i>Select a ticker below or type directly:</i>"
    ]
    return "\n".join(lines)


def format_weight_diffs(data: dict) -> str:
    """Format weight differences for Telegram message."""
    if data.get("error"):
        return f"⚠️ <b>Error:</b> {data['error']}"

    merged_data = data.get("merged_data", {})
    current_weights = data.get("current_weights", {})
    targets = data.get("targets", {})
    total_usd = data.get("total_value_usd", 0)
    rate = data.get("exchange_rate", 0)

    diffs = calc_weight_diffs(merged_data, current_weights, targets, total_usd, rate)

    if not diffs:
        return "⚖️ <b>Portfolio Rebalancing</b>\n\nEverything is balanced!"

    sell_lines = []
    buy_lines = []

    for d in diffs:
        # Show top diffs or those > 0.5%
        if d['abs_diff'] < 0.005:
            continue

        ticker = d['ticker']
        msg = f"- <b>{ticker}</b>: {d['diff']*100:+.1f}% ({d['cur_w']*100:.1f}% -> {d['tgt_w']*100:.1f}%) | <b>Qty: {d['qty_diff']:+d}</b>"

        if d['diff'] < 0:
            sell_lines.append(msg)
        else:
            buy_lines.append(msg)

    lines = [f"⚖️ <b>Portfolio Rebalancing</b> (Total: ${total_usd/1000:,.1f}K)", ""]

    if sell_lines:
        lines.append("🔴 <b>SELL</b>")
        lines.extend(sell_lines)
        lines.append("")

    if buy_lines:
        lines.append("🟢 <b>BUY</b>")
        lines.extend(buy_lines)
        lines.append("")

    if not sell_lines and not buy_lines:
        lines.append("No significant differences found (>0.5%).")
    else:
        lines.append("<i>Significant changes (>0.5%) only</i>")

    return "\n".join(lines)


def format_ticker_detail(ticker: str, data: dict, portfolio_data: dict) -> str:
    """
    Format detailed ticker information for Telegram message.

    Args:
        ticker: Stock ticker symbol
        data: Merged data for this ticker from merged_data
        portfolio_data: Full portfolio data from get_portfolio()

    Returns:
        Formatted string with ticker details
    """

    qty = data.get("qty", 0)
    total_investment = data.get("total_investment", 0)
    currency = data.get("currency", "USD")
    name = data.get("name", ticker)

    # Calculate avg_price
    avg_price = total_investment / qty if qty > 0 else 0

    # Get cur_price - priority: merged_data (KIS balance API) -> WebSocket -> KIS price API
    cur_price = data.get("cur_price", 0)
    price_source = ""

    # Only try WebSocket/API fallback if merged_data doesn't have valid price
    if cur_price <= 0 and currency == "USD":
        from menu.raoeo.raoeo import get_current_price
        from menu.handle_account_info import fetch_price

        # Try WebSocket
        cur_price = get_current_price(ticker)
        if cur_price > 0:
            price_source = "WS"
        else:
            # Fallback to KIS API (fetch_price handles exchange internally)
            cur_price = fetch_price(ticker)
            price_source = "API" if cur_price > 0 else ""

    # Final fallback to avg_price if still 0
    if cur_price <= 0:
        cur_price = avg_price
        price_source = "Avg"

    # Calculate P&L
    current_value = qty * cur_price
    pnl = current_value - total_investment
    pnl_pct = (pnl / total_investment * 100) if total_investment > 0 else 0

    # Get weight info
    current_weights = portfolio_data.get("current_weights", {})
    targets = portfolio_data.get("targets", {})
    cur_weight = current_weights.get(ticker, 0) * 100
    tgt_weight = targets.get(ticker, 0) * 100
    weight_diff = tgt_weight - cur_weight

    # Currency symbol
    sym = "$" if currency == "USD" else "₩"

    # Format prices
    if currency == "USD":
        avg_str = f"{sym}{avg_price:,.2f}"
        cur_str = f"{sym}{cur_price:,.2f}"
        if price_source:
            cur_str += f" <i>({price_source})</i>"
        pnl_str = f"{sym}{pnl:+,.2f}"
    else:
        avg_str = f"{sym}{avg_price:,.0f}"
        cur_str = f"{sym}{cur_price:,.0f}"
        pnl_str = f"{sym}{pnl:+,.0f}"

    # P&L emoji
    pnl_emoji = "📈" if pnl >= 0 else "📉"

    lines = [
        f"📊 <b>{ticker}</b> ({name})",
        "",
        f"<b>Qty:</b> {qty:,.2f}" if qty != int(qty) else f"<b>Qty:</b> {int(qty):,}",
        f"<b>Avg Price:</b> {avg_str}",
        f"<b>Cur Price:</b> {cur_str}",
        "",
        f"{pnl_emoji} <b>P&L:</b> {pnl_str} ({pnl_pct:+.1f}%)",
        "",
        f"<b>Cur Weight:</b> {cur_weight:.2f}%",
        f"<b>Tgt Weight:</b> {tgt_weight:.2f}%",
        f"<b>Weight Diff:</b> {weight_diff:+.2f}%",
        "",
        "<i>Select another ticker or /cancel to exit</i>"
    ]

    return "\n".join(lines)


def format_ticker_not_in_portfolio(ticker: str, portfolio_data: dict) -> str:
    """
    Format info for a ticker not currently in portfolio.
    Shows current price (from WebSocket or KIS API fallback) and target weight.

    Args:
        ticker: Stock ticker symbol
        portfolio_data: Full portfolio data from get_portfolio()

    Returns:
        Formatted string with ticker info
    """
    from menu.raoeo.raoeo import get_current_price
    from menu.handle_account_info import fetch_price

    targets = portfolio_data.get("targets", {})
    tgt_weight = targets.get(ticker, 0) * 100

    # Try WebSocket first
    cur_price = get_current_price(ticker)
    price_source = "WebSocket"

    # Fallback to KIS API if WebSocket has no data
    if cur_price <= 0:
        cur_price = fetch_price(ticker)
        price_source = "API" if cur_price > 0 else ""

    lines = [
        f"📊 <b>{ticker}</b>",
        "",
        "<i>Not in current portfolio</i>",
        ""
    ]

    if cur_price > 0:
        lines.append(f"<b>Cur Price:</b> ${cur_price:,.2f} <i>({price_source})</i>")
    else:
        lines.append("<b>Cur Price:</b> <i>N/A</i>")

    lines.extend([
        "",
        f"<b>Tgt Weight:</b> {tgt_weight:.2f}%",
        "",
        "<i>Select another ticker or /cancel to exit</i>"
    ])

    return "\n".join(lines)


def build_ticker_keyboard(portfolio_data: dict) -> InlineKeyboardMarkup:
    """
    Build InlineKeyboard with tickers from stock_configuration.json
    where telegram_button is True.

    Args:
        portfolio_data: Full portfolio data from get_portfolio()

    Returns:
        InlineKeyboardMarkup with ticker buttons
    """
    import json
    import os

    # Load stock configuration
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "stock_configuration.json")
    button_tickers = []

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # Get tickers with telegram_button: true from both KR and US
        for region in ['KR', 'US']:
            for stock in config.get(region, []):
                if stock.get('telegram_button', False):
                    button_tickers.append(stock['ticker'])
    except Exception as e:
        logging.warning(f"Failed to load stock_configuration.json: {e}")
        # Fallback: use top tickers from portfolio
        merged_data = portfolio_data.get("merged_data", {})
        targets = portfolio_data.get("targets", {})
        ticker_weights = []
        for ticker, data in merged_data.items():
            if data.get("type") == "CASH" or "cash" in ticker.lower():
                continue
            tgt = targets.get(ticker, 0)
            ticker_weights.append((ticker, tgt))
        ticker_weights.sort(key=lambda x: x[1], reverse=True)
        button_tickers = [t[0] for t in ticker_weights[:8]]

    # Build keyboard (2 columns)
    keyboard = []
    for i in range(0, len(button_tickers), 2):
        row = [InlineKeyboardButton(button_tickers[i], callback_data=f"port_{button_tickers[i]}")]
        if i + 1 < len(button_tickers):
            row.append(InlineKeyboardButton(button_tickers[i+1], callback_data=f"port_{button_tickers[i+1]}"))
        keyboard.append(row)

    return InlineKeyboardMarkup(keyboard)


async def cmd_portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command handler for /portfolio - Entry point for ConversationHandler."""
    """Command handler for /portfolio - Entry point for ConversationHandler."""

    logging.info(f"[TG] Portfolio session started for user {update.effective_user.id}")
    # Get portfolio data and cache in user_data
    data = get_portfolio()
    context.user_data['portfolio_data'] = data

    # Format summary message
    msg = format_portfolio_summary(data)

    # Build keyboard
    keyboard = build_ticker_keyboard(data)

    sent_msg = await wrap_reply(update, msg, parse_mode='HTML', reply_markup=keyboard)
    if sent_msg:
        context.user_data['last_port_msg_id'] = sent_msg.message_id

    return SELECT_TICKER


async def handle_ticker_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle InlineKeyboard button clicks for ticker selection."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    logging.info(f"[TG] Callback: {callback_data}")

    # Handle cancel
    if callback_data == "port_cancel":
        await wrap_edit(update, "👋 Portfolio session closed.", parse_mode='HTML')
        context.user_data.pop('portfolio_data', None)
        return ConversationHandler.END

    # Extract ticker from callback_data (format: port_TICKER)
    if not callback_data.startswith("port_"):
        return SELECT_TICKER

    ticker = callback_data[5:]  # Remove "port_" prefix

    # Get cached portfolio data
    portfolio_data = context.user_data.get('portfolio_data', {})
    merged_data = portfolio_data.get("merged_data", {})

    # Find ticker (case-insensitive)
    ticker_upper = ticker.upper()
    found_ticker = None
    for t in merged_data.keys():
        if t.upper() == ticker_upper:
            found_ticker = t
            break

    if not found_ticker:
        detail_msg = format_ticker_not_in_portfolio(ticker, portfolio_data)
        keyboard = build_ticker_keyboard(portfolio_data)
        await wrap_edit(update, detail_msg, parse_mode='HTML', reply_markup=keyboard)
        return SELECT_TICKER

    # Format and send ticker detail
    ticker_data = merged_data[found_ticker]
    detail_msg = format_ticker_detail(found_ticker, ticker_data, portfolio_data)

    # Edit message to show detail
    keyboard = build_ticker_keyboard(portfolio_data)
    sent_msg = await wrap_edit(update, detail_msg, parse_mode='HTML', reply_markup=keyboard)
    if sent_msg:
        context.user_data['last_port_msg_id'] = sent_msg.message_id

    return SELECT_TICKER


async def handle_ticker_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text input for ticker selection."""
    """Handle text input for ticker selection."""

    ticker_input = update.message.text.strip().upper()

    # Get cached portfolio data
    portfolio_data = context.user_data.get('portfolio_data', {})
    merged_data = portfolio_data.get("merged_data", {})

    # Find ticker (case-insensitive)
    found_ticker = None
    for t in merged_data.keys():
        if t.upper() == ticker_input:
            found_ticker = t
            break

    if not found_ticker:
        # Ticker not in portfolio - show target weight info
        detail_msg = format_ticker_not_in_portfolio(ticker_input, portfolio_data)
        keyboard = build_ticker_keyboard(portfolio_data)
        sent_msg = await wrap_reply(update, detail_msg, parse_mode='HTML', reply_markup=keyboard)
        if sent_msg:
            context.user_data['last_port_msg_id'] = sent_msg.message_id
        return SELECT_TICKER

    # Format and send ticker detail
    ticker_data = merged_data[found_ticker]
    detail_msg = format_ticker_detail(found_ticker, ticker_data, portfolio_data)

    keyboard = build_ticker_keyboard(portfolio_data)
    sent_msg = await wrap_reply(update, detail_msg, parse_mode='HTML', reply_markup=keyboard)
    if sent_msg:
        context.user_data['last_port_msg_id'] = sent_msg.message_id

    return SELECT_TICKER


async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command to exit conversation."""
    context.user_data.pop('portfolio_data', None)
    await wrap_reply(update, "👋 Portfolio session closed.", parse_mode='HTML')
    return ConversationHandler.END


async def timeout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle conversation timeout."""
    display.add_alert("[TG] Session Expired", "INFO")
    logging.info("[TG] Portfolio session timed out")

    try:
        context.user_data.pop('portfolio_data', None)
        last_msg_id = context.user_data.pop('last_port_msg_id', None)
        if last_msg_id:
            from .telegram_bot import _chat_id
            if _chat_id:
                await context.bot.edit_message_text(
                    chat_id=_chat_id,
                    message_id=last_msg_id,
                    text="⏳ <b>Session Expired.</b>",
                    parse_mode='HTML'
                )
    except Exception as e:
        logging.error(f"[TG] Timeout process error: {e}")

    return ConversationHandler.END


async def cmd_portfolio_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command handler for /portfolio_weight."""
    # Run silently
    data = get_portfolio()
    msg = format_weight_diffs(data)
    await wrap_reply(update, msg, parse_mode='HTML')


def register_portfolio_handlers(app: Application):
    """Register Portfolio command handlers."""
    # ConversationHandler for /portfolio
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("portfolio", cmd_portfolio)],
        states={
            SELECT_TICKER: [
                CallbackQueryHandler(handle_ticker_callback, pattern=r'^port_'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ticker_text)
            ],
            ConversationHandler.TIMEOUT: [TypeHandler(object, timeout_handler)]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_handler)
        ],
        conversation_timeout=60,
        per_message=False,
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("portfolio_weight", cmd_portfolio_weight))


def get_portfolio_commands_desc() -> str:
    """Return Portfolio command descriptions for init message."""
    return (
        "/portfolio - Portfolio check (interactive)\n"
        "/portfolio_weight - Rebalancing suggestions"
    )
