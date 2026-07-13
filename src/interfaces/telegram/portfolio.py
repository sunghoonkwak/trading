# -*- coding: utf-8 -*-
"""
Telegram Portfolio Module

This module handles portfolio specific Telegram commands with ConversationHandler
for interactive ticker selection.
"""
import logging
import warnings
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from telegram.warnings import PTBUserWarning

warnings.filterwarnings("ignore", category=PTBUserWarning)
import asyncio
from typing import Any, Callable, cast

from telegram import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    TypeHandler,
    filters,
)

from application.ports import MarketPriceReader, OpenOrderReader, PortfolioReader
from interfaces.telegram.portfolio_formatter import format_portfolio_summary

from .utils import wrap_edit, wrap_edit_message, wrap_reply

# Conversation states
SELECT_TICKER = 0
@dataclass(frozen=True)
class PortfolioCommandDependencies:
    """Portfolio collaborators owned by one Telegram handler registration."""

    reader: PortfolioReader
    market_reader: MarketPriceReader
    order_reader: OpenOrderReader
    get_weight_diffs: Any
    refresh_gsheet_cache: Any
    load_stock_configuration: Callable[[], dict]


async def _run_in_executor(func, *args):
    """Run a blocking application or infrastructure call."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func, *args)


def format_weight_diffs(diffs: list, total_usd: float, cash_info: dict) -> str:
    """
    Format weight differences for Telegram message.
    Args:
        diffs: List of diffs.
        total_usd: Total portfolio value in USD.
        cash_info: Dict with current/target cash weights.
    Returns:
        Formatted string with weight differences
    """
    # Get F&G index
    try:
        from utils.market_utils import get_fear_and_greed
        fg_index = int(get_fear_and_greed())
    except ImportError:
        fg_index = 50

    if not diffs:
        return f"⚖️ <b>Portfolio Rebalancing</b> (F&G: {fg_index})\n\nEverything is balanced!"

    sell_lines = []
    buy_lines = []

    def format_usd_k(value: float) -> str:
        return f"${value/1000:,.1f}K"

    for d in diffs:
        # Show top diffs if absolute diff >= 0.5% OR relative diff >= 30%
        is_significant_abs = d['abs_diff'] >= 0.005
        is_significant_rel = (d['tgt_w'] > 0 and d['abs_diff'] / d['tgt_w'] >= 0.3)

        if not (is_significant_abs or is_significant_rel):
            continue

        ticker = d['ticker']
        # For Korean stocks (numeric ticker), show name instead
        display_name = d.get('name', ticker) if ticker.isdigit() else ticker
        if d.get("is_group"):
            group_name = d.get("name", ticker)
            current_value = format_usd_k(d.get("current_value_usd", d["cur_w"] * total_usd))
            target_value = format_usd_k(d.get("target_value_usd", d["tgt_w"] * total_usd))
            msg = (
                f"- <b>{group_name}</b> [{ticker}]: "
                f"{d['diff']*100:+.1f}% ({d['cur_w']*100:.1f}% -> {d['tgt_w']*100:.1f}%) "
                f"| {current_value} → {target_value} "
                f"| <b>Qty: {d['qty_diff']:+d} {ticker}</b>"
            )
        else:
            msg = f"- <b>{display_name}</b>: {d['diff']*100:+.1f}% ({d['cur_w']*100:.1f}% -> {d['tgt_w']*100:.1f}%) | <b>Qty: {d['qty_diff']:+d}</b>"

        if d['diff'] < 0:
            sell_lines.append(msg)
        else:
            buy_lines.append(msg)

    lines = [f"⚖️ <b>Portfolio Rebalancing</b> (F&G: {fg_index} | Total: ${total_usd/1000:,.1f}K)"]

    # Add cash info line if available
    if cash_info:
        cur_cash = cash_info.get('current', 0) * 100
        tgt_cash = cash_info.get('target', 0) * 100
        lines.append(f"💵 <b>Cash</b>: {cur_cash:.1f}% → {tgt_cash:.1f}%")

    lines.append("")

    if sell_lines:
        lines.append("🔴 <b>SELL</b>")
        lines.extend(sell_lines)
        lines.append("")

    if buy_lines:
        lines.append("🟢 <b>BUY</b>")
        lines.extend(buy_lines)
        lines.append("")

    if not sell_lines and not buy_lines:
        lines.append("No significant differences found (>0.5% abs or >30% rel).")
    else:
        lines.append("<i>Significant changes (>0.5% abs or >30% rel) only</i>")

    return "\n".join(lines)


def format_ticker_detail(
    ticker: str,
    data: dict,
    portfolio_data: dict,
    market_reader: MarketPriceReader,
) -> str:
    """
    Format detailed ticker information for Telegram message.

    Args:
        ticker: Stock ticker symbol
        data: Merged data for this ticker from merged_data
        portfolio_data: Full portfolio data from get_portfolio_data()

    Returns:
        Formatted string with ticker details
    """

    qty = data.get("qty", 0)
    total_investment = data.get("total_investment", 0)
    currency = data.get("currency", "USD")
    name = data.get("name", ticker)

    # Calculate avg_price
    avg_price = total_investment / qty if qty > 0 else 0

    # Get cur_price - priority: merged_data (broker API) -> market data API
    cur_price = data.get("cur_price", 0)

    # Only try API fallback if merged_data doesn't have valid price
    if cur_price <= 0 and currency == "USD":
        cur_price = market_reader.get_current_price(ticker)
        if cur_price <= 0:
            cur_price = market_reader.fetch_price(ticker)

    # Final fallback to avg_price if still 0
    if cur_price <= 0:
        cur_price = avg_price

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


def format_ticker_not_in_portfolio(
    ticker: str,
    portfolio_data: dict,
    market_reader: MarketPriceReader,
) -> str:
    """
    Format info for a ticker not currently in portfolio.
    Shows current price and target weight.

    Args:
        ticker: Stock ticker symbol
        portfolio_data: Full portfolio data from get_portfolio_data()

    Returns:
        Formatted string with ticker info
    """
    targets = portfolio_data.get("targets", {})
    tgt_weight = targets.get(ticker, 0) * 100

    cur_price = market_reader.get_current_price(ticker)

    if cur_price <= 0:
        cur_price = market_reader.fetch_price(ticker)

    lines = [
        f"📊 <b>{ticker}</b>",
        "",
        "<i>Not in current portfolio</i>",
        ""
    ]

    if cur_price > 0:
        lines.append(f"<b>Cur Price:</b> ${cur_price:,.2f}")
    else:
        lines.append("<b>Cur Price:</b> <i>N/A</i>")

    lines.extend([
        "",
        f"<b>Tgt Weight:</b> {tgt_weight:.2f}%",
        "",
        "<i>Select another ticker or /cancel to exit</i>"
    ])

    return "\n".join(lines)


def build_ticker_keyboard(
    portfolio_data: dict,
    load_stock_configuration: Callable[[], dict],
) -> InlineKeyboardMarkup:
    """
    Build InlineKeyboard with tickers from stock_configuration.json
    where telegram_button is True.

    Args:
        portfolio_data: Full portfolio data from get_portfolio_data()

    Returns:
        InlineKeyboardMarkup with ticker buttons
    """
    button_tickers = []

    try:
        config = load_stock_configuration()

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
        button_tickers = [t_w[0] for t_w in ticker_weights[:8]]

    # Build keyboard (2 columns)
    keyboard = []
    for i in range(0, len(button_tickers), 2):
        row = [InlineKeyboardButton(button_tickers[i], callback_data=f"port_{button_tickers[i]}")]
        if i + 1 < len(button_tickers):
            row.append(InlineKeyboardButton(button_tickers[i+1], callback_data=f"port_{button_tickers[i+1]}"))
        keyboard.append(row)

    return InlineKeyboardMarkup(keyboard)


async def _cmd_portfolio(
    dependencies: PortfolioCommandDependencies,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Command handler for /portfolio - Entry point for ConversationHandler."""

    logging.info("[TG] /portfolio from user")
    user_data = cast(dict[Any, Any], context.user_data)
    try:
        # Get portfolio data and cache in user_data
        data = await _run_in_executor(dependencies.reader.get_portfolio_data)
        user_data['portfolio_data'] = data

        # Format summary message
        msg = format_portfolio_summary(data)

        # Build keyboard
        keyboard = build_ticker_keyboard(
            data, dependencies.load_stock_configuration
        )

        sent_msg = await wrap_reply(update, msg, parse_mode='HTML', reply_markup=keyboard)
        if sent_msg:
            user_data['last_port_msg_id'] = sent_msg.message_id

        return SELECT_TICKER
    except Exception as e:
        logging.error(f"[TG] cmd_portfolio failed: {e}")
        user_data.pop('portfolio_data', None)
        return ConversationHandler.END


async def _handle_ticker_callback(
    dependencies: PortfolioCommandDependencies,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Handle InlineKeyboard button clicks for ticker selection."""
    user_data = cast(dict[Any, Any], context.user_data)
    try:
        query = cast(CallbackQuery, update.callback_query)
        await query.answer()

        callback_data = cast(str, query.data)
        logging.info(f"[TG] Callback: {callback_data}")

        # Handle cancel
        if callback_data == "port_cancel":
            await wrap_edit(update, "👋 Portfolio session closed.", parse_mode='HTML')
            user_data.pop('portfolio_data', None)
            return ConversationHandler.END

        # Extract ticker from callback_data (format: port_TICKER)
        if not callback_data.startswith("port_"):
            return SELECT_TICKER

        ticker = callback_data[5:]  # Remove "port_" prefix

        # Get cached portfolio data
        portfolio_data = user_data.get('portfolio_data', {})
        merged_data = portfolio_data.get("merged_data", {})

        # Find ticker (case-insensitive)
        ticker_upper = ticker.upper()
        found_ticker = None
        for t in merged_data.keys():
            if t.upper() == ticker_upper:
                found_ticker = t
                break

        if not found_ticker:
            detail_msg = format_ticker_not_in_portfolio(
                ticker, portfolio_data, dependencies.market_reader
            )
            keyboard = build_ticker_keyboard(
                portfolio_data, dependencies.load_stock_configuration
            )
            await wrap_edit(update, detail_msg, parse_mode='HTML', reply_markup=keyboard)
            return SELECT_TICKER

        # Format and send ticker detail
        ticker_data = merged_data[found_ticker]
        detail_msg = format_ticker_detail(
            found_ticker, ticker_data, portfolio_data, dependencies.market_reader
        )

        # Edit message to show detail
        keyboard = build_ticker_keyboard(
            portfolio_data, dependencies.load_stock_configuration
        )
        sent_msg = await wrap_edit(update, detail_msg, parse_mode='HTML', reply_markup=keyboard)
        if sent_msg:
            user_data['last_port_msg_id'] = sent_msg.message_id

        return SELECT_TICKER
    except Exception as e:
        logging.error(f"[TG] handle_ticker_callback failed: {e}")
        return SELECT_TICKER


async def _handle_ticker_text(
    dependencies: PortfolioCommandDependencies,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Handle text input for ticker selection."""
    user_data = cast(dict[Any, Any], context.user_data)
    try:
        message = cast(Message, update.message)
        ticker_input = cast(str, message.text).strip().upper()

        # Get cached portfolio data
        portfolio_data = user_data.get('portfolio_data', {})
        merged_data = portfolio_data.get("merged_data", {})

        # Find ticker (case-insensitive)
        found_ticker = None
        for t in merged_data.keys():
            if t.upper() == ticker_input:
                found_ticker = t
                break

        if not found_ticker:
            # Ticker not in portfolio - show target weight info
            detail_msg = format_ticker_not_in_portfolio(
                ticker_input, portfolio_data, dependencies.market_reader
            )
            keyboard = build_ticker_keyboard(
                portfolio_data, dependencies.load_stock_configuration
            )
            sent_msg = await wrap_reply(update, detail_msg, parse_mode='HTML', reply_markup=keyboard)
            if sent_msg:
                user_data['last_port_msg_id'] = sent_msg.message_id
            return SELECT_TICKER

        # Format and send ticker detail
        ticker_data = merged_data[found_ticker]
        detail_msg = format_ticker_detail(
            found_ticker, ticker_data, portfolio_data, dependencies.market_reader
        )

        keyboard = build_ticker_keyboard(
            portfolio_data, dependencies.load_stock_configuration
        )
        sent_msg = await wrap_reply(update, detail_msg, parse_mode='HTML', reply_markup=keyboard)
        if sent_msg:
            user_data['last_port_msg_id'] = sent_msg.message_id

        return SELECT_TICKER
    except Exception as e:
        logging.error(f"[TG] handle_ticker_text failed: {e}")
        return SELECT_TICKER


async def _cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command to exit conversation."""
    logging.info("[TG] /cancel from user")
    user_data = cast(dict[Any, Any], context.user_data)
    user_data.pop('portfolio_data', None)
    try:
        await wrap_reply(update, "👋 Portfolio session closed.", parse_mode='HTML')
    except Exception as e:
        logging.error(f"[TG] cancel_handler reply failed: {e}")
    return ConversationHandler.END


async def _timeout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle conversation timeout."""
    logging.info("[TG] Portfolio session timed out")
    user_data = cast(dict[Any, Any], context.user_data)

    try:
        user_data.pop('portfolio_data', None)
        last_msg_id = user_data.pop('last_port_msg_id', None)
        if last_msg_id:
            from .bot import _chat_id
            if _chat_id:
                await wrap_edit_message(
                    chat_id=_chat_id,
                    message_id=last_msg_id,
                    text="⏳ <b>Session Expired.</b>",
                    parse_mode='HTML'
                )
    except Exception as e:
        logging.error(f"[TG] Timeout process error: {e}")

    return ConversationHandler.END


def format_placed_orders(df, num_us: int, num_kr: int, num_toss: int | None = None) -> str:
    """Format open orders for Telegram message."""
    if df.empty:
        return "📋 <b>Open Orders</b>\n\nNo open orders."

    def as_float(value, default=0.0):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        return default if number != number else number

    def first_value(*values):
        for value in values:
            if value is None:
                continue
            if isinstance(value, float) and value != value:
                continue
            if isinstance(value, str) and value.strip() in {"", "Unknown", "nan", "None"}:
                continue
            return value
        return None

    def format_quantity(value):
        value = first_value(value, 0)
        text = str(value).strip()
        try:
            quantity = Decimal(text)
        except (InvalidOperation, ValueError):
            return text
        if quantity == quantity.to_integral_value():
            return str(quantity.quantize(Decimal("1")))
        return format(quantity.normalize(), "f")

    def toss_order_label(row_lower):
        order_type = str(row_lower.get('ordertype', row_lower.get('order_type', ''))).upper()
        time_in_force = str(row_lower.get('timeinforce', row_lower.get('time_in_force', ''))).upper()
        if order_type == "LIMIT" and time_in_force == "CLS":
            return "LOC"
        return order_type

    def row_to_order(row):
        market = row.get('_market', 'US')
        row_lower = {k.lower(): v for k, v in row.items()}

        pdno = first_value(
            row_lower.get('pdno'),
            row_lower.get('stck_shrn_iscd'),
            row_lower.get('symbol'),
            'Unknown',
        )

        if market == "TOSS":
            broker = "Toss"
        else:
            broker = "KIS"

        if market == "KR":
            is_buy = row_lower.get('sll_buy_dvsn_cd') == '02'
            side = "Buy" if is_buy else "Sell"
            order_type = "매수" if is_buy else "매도"
            price = f"₩{int(float(row_lower.get('ord_unpr', '0'))):,}"
            qty = str(row_lower.get('psbl_qty', 0))
        elif market == "TOSS":
            side_value = str(row_lower.get('side', '')).upper()
            side = "Buy" if side_value == "BUY" else "Sell"
            order_type = toss_order_label(row_lower)
            if order_type == "MARKET":
                order_type = ""
            p_val = row_lower.get('price')
            p_float = as_float(p_val)
            if p_float > 0:
                currency = "₩" if str(pdno).isdigit() else "$"
                price = f"{currency}{p_float:,.0f}" if currency == "₩" else f"{currency}{p_float:,.2f}"
            else:
                price = "Market"
            q_val = first_value(
                row_lower.get('remainingquantity'),
                row_lower.get('remaining_quantity'),
                row_lower.get('quantity'),
                row_lower.get('orderquantity'),
                0,
            )
            qty = format_quantity(q_val)
        else:
            is_buy = row_lower.get('sll_buy_dvsn_cd') == '02'
            side_text = str(row_lower.get('sll_buy_dvsn_cd_name', row_lower.get('sll_buy_dvsn_name', ''))).strip()
            order_type = "LOC" if "LOC" in side_text.upper() else ""
            side = "Buy" if is_buy else "Sell"
            p_val = row_lower.get('ft_ord_unpr3', row_lower.get('ft_ord_unpr4', row_lower.get('ovrs_ord_unpr', row_lower.get('ord_unpr', '0'))))
            price = f"${float(p_val):,.2f}" if float(p_val) > 0 else "Market"
            q_val = row_lower.get('nccs_qty', row_lower.get('ft_ord_qty4', row_lower.get('ord_qty', 0)))
            qty = str(int(float(q_val)))

        return {
            "broker": broker,
            "ticker": pdno,
            "side": side,
            "order_type": order_type,
            "price": price,
            "qty": qty,
        }

    def append_grouped_orders(lines, grouped):
        for idx, (ticker, group) in enumerate(grouped.items()):
            if idx > 0:
                lines.append("")

            lines.append(f"<b>{ticker}</b>")

            for side, emoji in (("Sell", "🔴"), ("Buy", "🟢")):
                side_orders = group[side]
                if not side_orders:
                    continue

                lines.append(f"{emoji} <b>{side}</b>")
                label_width = max(len(order["order_type"]) for order in side_orders)
                for order in side_orders:
                    if order["order_type"]:
                        label = order["order_type"].ljust(label_width)
                        lines.append(f"  {label}  {order['qty']} @ {order['price']}")
                    else:
                        lines.append(f"  {order['qty']} @ {order['price']}")

    def grouped_by_ticker(orders_for_broker):
        grouped: dict[str, Any] = {}
        for order in orders_for_broker:
            grouped.setdefault(
                order["ticker"],
                {"Buy": [], "Sell": []},
            )[order["side"]].append(order)
        return grouped

    orders = [row_to_order(row) for _, row in df.iterrows()]

    counts = f"US: {num_us} / KR: {num_kr}"
    if num_toss is not None:
        counts = f"{counts} / Toss: {num_toss}"
    lines = [
        f"📋 <b>Open Orders</b> ({counts})",
        "",
    ]

    if num_toss is None:
        append_grouped_orders(lines, grouped_by_ticker(orders))
    else:
        first_section = True
        for broker in ("KIS", "Toss"):
            broker_orders = [order for order in orders if order["broker"] == broker]
            if not broker_orders:
                continue
            if not first_section:
                lines.append("")
            lines.append(f"<b>{broker}</b>")
            lines.append("")
            append_grouped_orders(lines, grouped_by_ticker(broker_orders))
            first_section = False

    return "\n".join(lines)


async def _cmd_placed_orders(
    dependencies: PortfolioCommandDependencies,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Command handler for /placed_orders - Show open orders."""
    logging.info("[TG] /placed_orders from user")
    try:
        df, num_us, num_kr, num_toss = await _run_in_executor(
            dependencies.order_reader.fetch_open_orders
        )
        msg = format_placed_orders(df, num_us, num_kr, num_toss)
        await wrap_reply(update, msg, parse_mode='HTML')
    except Exception as e:
        logging.error(f"[TG] cmd_placed_orders failed: {e}")


async def _cmd_portfolio_weight(
    dependencies: PortfolioCommandDependencies,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Command handler for /portfolio_weight."""
    logging.info("[TG] /portfolio_weight from user")
    try:
        diffs, total_usd, cash_info = await _run_in_executor(
            dependencies.get_weight_diffs, "all"
        )
        msg = format_weight_diffs(diffs, total_usd, cash_info)
        await wrap_reply(update, msg, parse_mode='HTML')
    except Exception as e:
        logging.error(f"[TG] cmd_portfolio_weight failed: {e}")


async def _cmd_gsheet(
    dependencies: PortfolioCommandDependencies,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Command handler for /gsheet - refresh cached GSheet source data."""
    logging.info("[TG] /gsheet from user")
    try:
        result = await _run_in_executor(dependencies.refresh_gsheet_cache)
        status = (
            "✅ <b>GSheet cache updated</b>"
            if result["success"]
            else "⚠️ <b>GSheet cache updated with warnings</b>"
        )
        lines = [
            status,
            "",
            f"Holdings: {result['holdings_count']}",
            f"Cash rows: {result['cash_count']}",
            f"Accounts: {result['accounts_count']}",
        ]
        if result.get("last_updated"):
            lines.append(f"Updated: <code>{result['last_updated']}</code>")
        if result.get("error"):
            lines.extend(["", f"Warning: <code>{result['error']}</code>"])
        await wrap_reply(update, "\n".join(lines), parse_mode='HTML')
    except Exception as e:
        logging.error(f"[TG] cmd_gsheet failed: {e}")
        await wrap_reply(
            update,
            f"⚠️ <b>GSheet refresh failed:</b> <code>{e}</code>",
            parse_mode='HTML',
        )


class PortfolioCommandHandler:
    """Telegram portfolio handlers with one explicit dependency composition."""

    def __init__(self, dependencies: PortfolioCommandDependencies):
        self._dependencies = dependencies

    async def cmd_portfolio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await _cmd_portfolio(self._dependencies, update, context)

    async def handle_ticker_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        return await _handle_ticker_callback(self._dependencies, update, context)

    async def handle_ticker_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await _handle_ticker_text(self._dependencies, update, context)

    async def cancel_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await _cancel_handler(update, context)

    async def timeout_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await _timeout_handler(update, context)

    async def cmd_placed_orders(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await _cmd_placed_orders(self._dependencies, update, context)

    async def cmd_portfolio_weight(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        return await _cmd_portfolio_weight(self._dependencies, update, context)

    async def cmd_gsheet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await _cmd_gsheet(self._dependencies, update, context)

    def format_ticker_detail(self, ticker: str, data: dict, portfolio_data: dict) -> str:
        return format_ticker_detail(
            ticker, data, portfolio_data, self._dependencies.market_reader
        )

    def format_ticker_not_in_portfolio(self, ticker: str, portfolio_data: dict) -> str:
        return format_ticker_not_in_portfolio(
            ticker, portfolio_data, self._dependencies.market_reader
        )


def register_portfolio_handlers(
    app: Application,
    dependencies: PortfolioCommandDependencies,
):
    """Register Portfolio command handlers."""
    handler = PortfolioCommandHandler(dependencies)

    # ConversationHandler for /portfolio
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("portfolio", handler.cmd_portfolio)],
        states={
            SELECT_TICKER: [
                CallbackQueryHandler(handler.handle_ticker_callback, pattern=r'^port_'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handler.handle_ticker_text)
            ],
            ConversationHandler.TIMEOUT: [TypeHandler(Update, handler.timeout_handler)]
        },
        fallbacks=[
            CommandHandler("cancel", handler.cancel_handler)
        ],
        conversation_timeout=60,
        per_message=False,
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("gsheet", handler.cmd_gsheet))
    app.add_handler(CommandHandler("portfolio_weight", handler.cmd_portfolio_weight))
    app.add_handler(CommandHandler("placed_orders", handler.cmd_placed_orders))


def get_portfolio_commands_desc() -> str:
    """Return Portfolio command descriptions for init message."""
    return (
        "/portfolio - Portfolio check (interactive)\n"
        "/gsheet - Refresh cached GSheet data\n"
        "/portfolio_weight - Rebalancing suggestions\n"
        "/placed_orders - Show open orders"
    )
