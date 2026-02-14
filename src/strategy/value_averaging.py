# -*- coding: utf-8 -*-
"""
Value Averaging Strategy Module (Refactored)

This module implements the Value Averaging strategy logic.
It is now a pure calculation module without direct API dependencies.
"""
import logging
from typing import Dict, List, Tuple
from strategy.base import StrategyOrder, OrderSide

from constants import ORDER_TYPE_US_LOC, ORDER_TYPE_KR_MARKET

def calculate_orders(
    targets_config: Dict,
    portfolio: Dict,
    current_prices: Dict[str, float],
    history_data: List[Dict],
    today_date: str  # YYYY-MM-DD (US Eastern Time expected)
) -> Tuple[List[StrategyOrder], Dict[str, Dict]]:
    """
    Calculate buy/sell orders based on Value Averaging strategy.

    Args:
        targets_config: Configuration for each target ticker.
        portfolio: Current holdings data.
        current_prices: Current market price for each ticker.
        history_data: Loaded history list from JSON.
        today_date: The date string to use for history checks.

    Returns:
        Tuple[List[StrategyOrder], Dict[str, Dict]]:
            1. List of orders to be executed.
            2. Context dictionary for each ticker (for history saving/logging).
               Structure: { "SOXL": { "day_count": 5, "target_value": 1000, ... } }
    """
    orders: List[StrategyOrder] = []
    context_map: Dict[str, Dict] = {}

    if not targets_config:
        logging.warning("VA: No targets configured.")
        return orders, context_map

    for ticker, config in targets_config.items():
        if not config.get('enabled', True):
            continue

        # 1. Config Parameters
        daily_budget = config.get('daily_budget', 0)
        target_cap = config.get('target', 0)
        threshold_rate = config.get('threshold_rate', 0.15)
        
        # 2. Market Data
        cur_price = current_prices.get(ticker, 0.0)
        holding = portfolio.get(ticker, {})
        
        # Fallback to holding's price if current price is missing
        if cur_price <= 0:
            cur_price = float(holding.get('cur_price', 0.0))

        # Current Value Calculation
        # Assuming config currency matches the stock's currency (USD for US stocks)
        current_value_usd = float(holding.get('current_value_usd', 0.0))
        current_value_krw = float(holding.get('current_value_krw', 0.0))
        currency = holding.get('currency', 'USD')
        
        current_val = current_value_usd if currency == 'USD' else current_value_krw

        # 3. History & Day Count Logic
        ticker_hist_entry = None
        ticker_hist_date = None
        
        for entry in history_data:
            if ticker in entry.get('targets', {}):
                ticker_hist_entry = entry['targets'][ticker]
                ticker_hist_date = entry['date']
                break
        
        last_day_count = 0
        using_existing_today = False
        
        if ticker_hist_entry:
            last_day_count = int(ticker_hist_entry.get('day_count', 0))
            if ticker_hist_date == today_date:
                using_existing_today = True
        
        # Determine Day Count
        if using_existing_today:
            day_count = last_day_count
        else:
            day_count = last_day_count + 1

        # Check if already executed today
        executed_today = False
        if using_existing_today:
            results_list = ticker_hist_entry.get('results', [])
            for res in results_list:
                # Check for successful execution or specific skip types?
                # Original logic: checks if executed=True and type is not skip/None
                if res.get('executed') and res.get('type') not in ['skip', None]:
                    executed_today = True
                    break

        # 4. Target Calculation
        target_progress = day_count * daily_budget
        
        if target_cap > 0:
            target_value_accumulated = min(target_cap, target_progress)
        else:
            target_value_accumulated = target_progress
            
        daily_target_amount = target_value_accumulated - current_val
        
        # Divergence Calculation
        divergence_rate = 0.0
        if target_value_accumulated > 0:
            divergence_rate = abs(daily_target_amount) / target_value_accumulated
        elif daily_target_amount > 0:
            # Case: Start fresh (target=0 but need to buy)
            divergence_rate = 1.0

        # Context for logging/history
        context_map[ticker] = {
            "day_count": day_count,
            "daily_budget": daily_budget,
            "target_value": target_value_accumulated,
            "current_value": current_val,
            "daily_target_amount": daily_target_amount,
            "divergence_rate": divergence_rate,
            "threshold_rate": threshold_rate,
            "already_executed": executed_today
        }

        # 5. Generate Order
        if not executed_today and cur_price > 0:
            if divergence_rate >= threshold_rate:
                
                # BUY Case
                if daily_target_amount > 0:
                    buy_qty = int(daily_target_amount / cur_price)
                    if buy_qty > 0:
                        buy_price = round(cur_price * 1.05, 2)  # 5% buffer for LOC
                        orders.append(StrategyOrder(
                            symbol=ticker,
                            side=OrderSide.BUY,
                            quantity=buy_qty,
                            price=buy_price,
                            order_type=ORDER_TYPE_US_LOC,
                            reason=f"VA Day {day_count} (Target: {daily_target_amount:.2f})"
                        ))

                # SELL Case
                elif daily_target_amount < 0:
                    sell_amount = abs(daily_target_amount)
                    sell_qty = int(sell_amount / cur_price)
                    if sell_qty > 0:
                        orders.append(StrategyOrder(
                            symbol=ticker,
                            side=OrderSide.SELL,
                            quantity=sell_qty,
                            price=0.0,  # Market Price
                            order_type=ORDER_TYPE_KR_MARKET,
                            reason=f"VA Sell Day {day_count} (Target: {daily_target_amount:.2f})"
                        ))

    return orders, context_map
