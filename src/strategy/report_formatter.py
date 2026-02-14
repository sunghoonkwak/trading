# -*- coding: utf-8 -*-
"""
Strategy Report Formatter Module

Provides standardized formatting for strategy reports (Telegram message).
"""
from typing import Dict, List
from strategy.base import StrategyOrder, OrderSide

def format_strategy_report(raoeo_report: Dict, va_report: Dict) -> str:
    """Formats the combined strategy report."""
    lines = []
    today = raoeo_report.get('date', 'Today')
    
    lines.append(f"📊 <b>Strategy Report - {today}</b>")
    
    # --- RAOEO Section ---
    lines.append("\n🔹 <b>RAOEO</b>")
    
    # Check Global RAOEO Error
    if raoeo_report.get('error'):
        lines.append(f"  ⚠️ Error: {raoeo_report['error']}")
    else:
        raoeo_config = raoeo_report.get('config', {})
        holdings = raoeo_report.get('holdings', {})
        orders = raoeo_report.get('orders', [])
        
        # Group orders by ticker
        orders_by_ticker = {}
        for o in orders:
            orders_by_ticker.setdefault(o.symbol, []).append(o)
            
        for ticker, conf in raoeo_config.items():
            exch = conf.get('exchange', 'N/A')
            lines.append(f"\n  <b>{ticker} @ {exch}</b>")
            
            # Budget Info
            seed = float(conf.get('seed', 0))
            duration = int(conf.get('duration', 1))
            daily_budget = seed / duration if duration > 0 else 0
            lines.append(f"    Budget: ${daily_budget:.2f}/day (${seed:,.0f} / {duration}d)")
            
            # Holdings Info
            h_info = holdings.get(ticker, {})
            qty = h_info.get('qty', 0)
            avg_price = float(h_info.get('avg_price', 0.0))
            cur_price = float(h_info.get('cur_price', 0.0))
            lines.append(f"    Holdings: {qty} @ ${avg_price:.2f} (Cur: ${cur_price:.2f})")
            
            # Orders
            t_orders = orders_by_ticker.get(ticker, [])
            if t_orders:
                for o in t_orders:
                    lines.append(f"    • {o}")
                if raoeo_report.get('status') == 'market_holiday':
                    lines.append("    🚫 Market Holiday (Skipped)")
            elif raoeo_report.get('status') == 'market_holiday':
                lines.append("    🚫 Market Holiday")
            else:
                lines.append("    ✅ No orders needed.")

    # --- VA Section ---
    lines.append("\n🔹 <b>Value Averaging</b>")
    
    if va_report.get('error'):
        lines.append(f"  ⚠️ Error: {va_report['error']}")
    else:
        context_map = va_report.get('context', {})
        orders = va_report.get('orders', [])
        orders_by_ticker = {}
        for o in orders:
            orders_by_ticker.setdefault(o.symbol, []).append(o)
            
        # Iterate over context keys (calculated targets)
        for ticker, ctx in context_map.items():
            day_count = ctx.get('day_count', 0)
            target_val = ctx.get('target_value', 0)
            cur_val = ctx.get('current_value', 0)
            daily_target = ctx.get('daily_target_amount', 0)
            
            diff_str = f"${daily_target:,.0f}" if daily_target >= 0 else f"-${abs(daily_target):,.0f}"
            
            lines.append(f"\n  <b>{ticker}</b> (Day {day_count} | Tgt ${target_val:,.0f} | Cur ${cur_val:,.0f})")
            lines.append(f"    Diff: {diff_str}")
            
            t_orders = orders_by_ticker.get(ticker, [])
            if t_orders:
                for o in t_orders:
                    # Parse type code (34 -> LOC, 00 -> MARKET)
                    type_map = {"34": "LOC", "00": "MKT"}
                    type_str = type_map.get(o.order_type, o.order_type)
                    lines.append(f"    └ {o.side.name} {o.quantity} shares ({type_str})")
                
                # Show holiday warning if orders exist but it's holiday
                if va_report.get('status') == 'market_holiday':
                    lines.append("    🚫 Market Holiday (Will not execute)")
                    
            elif va_report.get('status') == 'market_holiday':
                lines.append("    🚫 Market Holiday")
            else:
                lines.append("    ✅ No orders needed.")

    # Execution Summary (if available)
    all_exec_results = []
    if raoeo_report.get('execution_results'):
        all_exec_results.extend(raoeo_report['execution_results'])
    if va_report.get('execution_results'):
        all_exec_results.extend(va_report['execution_results'])
        
    if all_exec_results:
        lines.append("\n" + "─" * 20)
        lines.append("<b>Execution Results:</b>")
        success_count = sum(1 for r in all_exec_results if r['success'])
        for res in all_exec_results:
            status = "✅" if res['success'] else "❌"
            order = res['order']
            msg = res.get('message', '')
            err_str = f" ({msg})" if not res['success'] else ""
            lines.append(f"  {status} {order.symbol} {order.side.name} {order.quantity} @ {order.price}{err_str}")
        lines.append(f"\n💾 Saved. <b>{success_count}/{len(all_exec_results)} succeeded</b>")

    return "\n".join(lines)
