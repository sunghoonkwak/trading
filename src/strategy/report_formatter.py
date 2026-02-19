# -*- coding: utf-8 -*-
"""
Strategy Report Formatter Module

Provides standardized formatting for strategy reports (Telegram message).
Uses the unified report structure with StrategyStatus enum.
"""
from typing import Dict, List
from strategy.base import StrategyOrder, StrategyStatus, OrderSide


def _format_market_status_line(report: Dict) -> str:
    """Format market status warning line if market is not open."""
    ms = report.get("market_status", {})
    if not ms.get("is_market_open", True):
        msg = ms.get("message", "Market Closed")
        return f"  ⚠️ <b>{msg}</b>\n  (Orders calculated but NOT executed)"
    return ""


def _format_execution_results(results: List[Dict]) -> List[str]:
    """Format execution results section."""
    lines = []
    if not results:
        return lines

    lines.append("\n" + "─" * 20)
    lines.append("<b>Execution Results:</b>")
    success_count = sum(1 for r in results if r['success'])
    for res in results:
        status = "✅" if res['success'] else "❌"
        order = res['order']
        msg = res.get('message', '')
        err_str = f" ({msg})" if not res['success'] else ""
        lines.append(f"  {status} {order.symbol} {order.side.name} {order.quantity} @ {order.price}{err_str}")
    lines.append(f"\n💾 Saved. <b>{success_count}/{len(results)} succeeded</b>")
    return lines


def _get_status_display(report: Dict) -> str:
    """Get display emoji and text for a strategy status."""
    status = report.get("status")
    if isinstance(status, StrategyStatus):
        status = status.value

    status_map = {
        "executed": "✅ All executed",
        "partial": "🔄 Partial (has failed orders)",
        "skipped": "✅ No orders needed",
        "holiday": "🚫 Market Holiday",
        "non_market_time": "⏰ Outside market hours",
        "disabled": "⚪ Disabled",
        "error": f"⚠️ Error: {report.get('error', 'Unknown')}",
        "already_done": "✅ All executed (History)",
    }
    return status_map.get(status, f"❓ {status}")


def format_strategy_report(raoeo_report: Dict, va_report: Dict) -> str:
    """Formats the combined strategy report (RAOEO + VA)."""
    lines = []
    today = raoeo_report.get('date', 'Today')

    lines.append(f"📊 <b>Strategy Report - {today}</b>")

    # --- RAOEO Section ---
    lines.append("\n🔹 <b>RAOEO</b>")
    ms_line = _format_market_status_line(raoeo_report)
    if ms_line:
        lines.append(ms_line)

    if raoeo_report.get('error'):
        lines.append(f"  ⚠️ Error: {raoeo_report['error']}")
    else:
        orders = raoeo_report.get('orders', [])
        succeeded = raoeo_report.get('succeeded_orders', [])
        pending = raoeo_report.get('pending_orders', [])
        info = raoeo_report.get('info', {})
        ticker_info = info.get('ticker_info', {})

        # Group orders by ticker
        orders_by_ticker = {}
        for o in orders:
            orders_by_ticker.setdefault(o.symbol, []).append(o)

        succeeded_symbols = {o.symbol for o in succeeded}

        if orders:
            for ticker, t_orders in orders_by_ticker.items():
                ti = ticker_info.get(ticker, {})
                phase = ti.get("phase", "")
                progress = ti.get("progress_pct", 0)
                cur_p = ti.get("cur_price", 0)
                avg_p = ti.get("avg_price", 0)

                profit_pct = 0.0
                if avg_p > 0:
                    profit_pct = (cur_p - avg_p) / avg_p * 100

                sign = "+" if profit_pct >= 0 else ""

                # Format: SOXL Phase1 (11.5%) cur $10.00 avg $9.00 (+11.11%)
                lines.append(f"\n  <b>{ticker}</b> {phase} ({progress:.1f}%) cur ${cur_p:.2f} avg ${avg_p:.2f} ({sign}{profit_pct:.2f}%)")

                for o in t_orders:
                    is_done = o in succeeded
                    icon = "✅" if is_done else "⏳"
                    lines.append(f"    {icon} {o}")

            # Status message
            lines.append(f"\n  {_get_status_display(raoeo_report)}")
        else:
            lines.append(f"\n  {_get_status_display(raoeo_report)}")

    # --- VA Section ---
    lines.append("\n🔹 <b>Value Averaging</b>")
    ms_line = _format_market_status_line(va_report)
    if ms_line:
        lines.append(ms_line)

    if va_report.get('error'):
        lines.append(f"  ⚠️ Error: {va_report['error']}")
    else:
        context_map = va_report.get('info', {}).get('context_map', {})
        orders = va_report.get('orders', [])

        orders_by_ticker = {}
        for o in orders:
            orders_by_ticker.setdefault(o.symbol, []).append(o)

        if context_map:
            for ticker, ctx in context_map.items():
                day_count = ctx.get('day_count', 0)
                target_val = ctx.get('target_value', 0)
                cur_val = ctx.get('current_value', 0)
                daily_target = ctx.get('daily_target_amount', 0)

                cur_p = ctx.get('cur_price', 0)
                avg_p = ctx.get('avg_price', 0)
                profit_pct = 0.0
                if avg_p > 0:
                    profit_pct = (cur_p - avg_p) / avg_p * 100
                sign = "+" if profit_pct >= 0 else ""

                diff_str = f"${daily_target:,.0f}" if daily_target >= 0 else f"-${abs(daily_target):,.0f}"

                lines.append(f"\n  <b>{ticker}</b> (Day {day_count}) cur ${cur_p:.2f} avg ${avg_p:.2f} ({sign}{profit_pct:.2f}%)")
                lines.append(f"    Tgt ${target_val:,.0f} | Cur ${cur_val:,.0f} | Diff {diff_str}")

                t_orders = orders_by_ticker.get(ticker, [])
                if t_orders:
                    for o in t_orders:
                        type_map = {"34": "LOC", "00": "MKT"}
                        type_str = type_map.get(o.order_type, o.order_type)
                        lines.append(f"    └ {o.side.name} {o.quantity} shares ({type_str})")
                else:
                    lines.append("    ✅ No orders needed.")

        lines.append(f"\n  {_get_status_display(va_report)}")

    # Execution Summary
    all_exec_results = []
    if raoeo_report.get('execution_results'):
        all_exec_results.extend(raoeo_report['execution_results'])
    if va_report.get('execution_results'):
        all_exec_results.extend(va_report['execution_results'])

    lines.extend(_format_execution_results(all_exec_results))

    return "\n".join(lines)


def format_rebalancing_report(reb_report: Dict) -> str:
    """Formats the rebalancing strategy report."""
    lines = []
    today = reb_report.get('date', 'Today')
    lines.append(f"⚖️ <b>Rebalancing Report - {today}</b>")

    if reb_report.get('error'):
        lines.append(f"  ⚠️ Error: {reb_report['error']}")
        return "\n".join(lines)

    status = reb_report.get('status')
    if isinstance(status, StrategyStatus):
        status_val = status.value
    else:
        status_val = status

    if status_val == 'disabled':
        lines.append("  ⚪ Disabled")
        return "\n".join(lines)

    # Market status warning
    lines.append(_format_market_status_line(reb_report))

    # Show Header Info
    info = reb_report.get('info', {})
    if info:
        seed = info.get('seed', 0)
        cash = info.get('usd_cash', 0)
        avail = info.get('total_available', 0)
        if seed:
            lines.append(f"  🎯 <b>Target Seed: ${seed:,.0f}</b>")
        if avail or cash:
            lines.append(f"  💰 <b>Available Cash: ${avail:,.2f}</b> (Pure: ${cash:,.2f})")

        if info.get('scale_factor', 1.0) < 1.0:
            lines.append(f"  ⚠️ Scaled by {info['scale_factor']*100:.1f}% due to cash limit")
        lines.append("")

    # Asset status
    asset_status = info.get('asset_status', {})
    if asset_status:
        lines.append("  <b>Current KIS Holdings & Weights:</b>")
        for ticker, data in asset_status.items():
            cur_w = data.get('cur_w', 0)
            tgt_w = data.get('target_w', 0)
            diff_w = data.get('diff_w', 0)
            qty = data.get('qty', 0)
            val = data.get('cur_val', 0)

            cur_p = data.get('cur_price', 0)
            avg_p = data.get('avg_price', 0)
            profit_pct = 0.0
            if avg_p > 0:
                profit_pct = (cur_p - avg_p) / avg_p * 100
            sign = "+" if profit_pct >= 0 else ""

            diff_sign = "+" if diff_w > 0 else ""
            lines.append(f"    • {ticker}: {cur_w}% ({diff_sign}{diff_w}%p) | {qty}sh (${val:,.1f})")
            lines.append(f"      cur ${cur_p:.2f} avg ${avg_p:.2f} ({sign}{profit_pct:.2f}%)")
        lines.append("")

    # Status display
    lines.append(f"  {_get_status_display(reb_report)}")

    # Orders List
    orders = reb_report.get('orders', [])
    if orders and status_val not in ('executed',):
        lines.append("\n  <b>Proposed Orders:</b>")
        for o in orders:
            lines.append(f"    • {o}")

    # Execution Results
    lines.extend(_format_execution_results(reb_report.get('execution_results', [])))

    return "\n".join(lines)
