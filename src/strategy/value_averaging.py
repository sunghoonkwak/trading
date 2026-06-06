# -*- coding: utf-8 -*-
"""
Value Averaging Strategy Module (Refactored)

This module implements the Value Averaging strategy logic.
It is now a pure calculation module without direct API dependencies.
"""
import logging
from typing import Dict, List, Optional, Tuple
from strategy.base import StrategyOrder, OrderSide
from utils.price_utils import resolve_current_price

from core.constants import ORDER_TYPE_US_LOC, ORDER_TYPE_US_LIMIT


def _current_value(holding: Dict) -> float:
    current_value_usd = float(holding.get('current_value_usd', 0.0))
    current_value_krw = float(holding.get('current_value_krw', 0.0))
    currency = holding.get('currency', 'USD')
    return current_value_usd if currency == 'USD' else current_value_krw


def _find_ticker_history(
    ticker: str,
    history_data: List[Dict],
) -> Tuple[Optional[Dict], Optional[str]]:
    for entry in history_data:
        va_context = entry.get('targets', {}).get('va', {}).get('targets_context', {})
        if ticker in va_context:
            return va_context[ticker], entry['date']

        if ticker in entry.get('targets', {}):
            return entry['targets'][ticker], entry['date']

    return None, None


def _resolve_day_count(
    ticker_hist_entry: Optional[Dict],
    ticker_hist_date: Optional[str],
    today_date: str,
) -> Tuple[int, bool]:
    last_day_count = 0
    using_existing_today = False

    if ticker_hist_entry:
        last_day_count = int(ticker_hist_entry.get('day_count', 0))
        using_existing_today = ticker_hist_date == today_date

    if using_existing_today:
        return last_day_count, True
    return last_day_count + 1, False


def _already_executed_today(
    ticker_hist_entry: Optional[Dict],
    using_existing_today: bool,
) -> bool:
    if not using_existing_today or not ticker_hist_entry:
        return False

    for result in ticker_hist_entry.get('results', []):
        is_success = result.get('success', result.get('executed', False))
        if is_success and result.get('type') not in ['skip', None]:
            return True

    return False


def _target_value(day_count: int, daily_budget: float, target_cap: float) -> float:
    target_progress = day_count * daily_budget
    if target_cap > 0:
        return min(target_cap, target_progress)
    return target_progress


def _divergence_rate(daily_target_amount: float, target_value_accumulated: float) -> float:
    if target_value_accumulated > 0:
        return abs(daily_target_amount) / target_value_accumulated
    if daily_target_amount > 0:
        return 1.0
    return 0.0


def _build_context(
    day_count: int,
    daily_budget: float,
    target_value_accumulated: float,
    current_val: float,
    daily_target_amount: float,
    divergence_rate: float,
    threshold_rate: float,
    executed_today: bool,
    cur_price: float,
    avg_price: float,
) -> Dict:
    return {
        "day_count": day_count,
        "daily_budget": daily_budget,
        "target_value": target_value_accumulated,
        "current_value": current_val,
        "daily_target_amount": daily_target_amount,
        "divergence_rate": divergence_rate,
        "threshold_rate": threshold_rate,
        "already_executed": executed_today,
        "cur_price": cur_price,
        "avg_price": avg_price,
    }


def _build_order(
    ticker: str,
    day_count: int,
    cur_price: float,
    daily_target_amount: float,
) -> Optional[StrategyOrder]:
    if daily_target_amount > 0:
        buy_qty = int(daily_target_amount / cur_price)
        if buy_qty > 0:
            buy_price = round(cur_price * 1.05, 2)
            return StrategyOrder(
                symbol=ticker,
                side=OrderSide.BUY,
                quantity=buy_qty,
                price=buy_price,
                order_type=ORDER_TYPE_US_LOC,
                reason=f"VA Day {day_count} (Target: {daily_target_amount:.2f})",
            )

    elif daily_target_amount < 0:
        sell_amount = abs(daily_target_amount)
        sell_qty = int(sell_amount / cur_price)
        if sell_qty > 0:
            return StrategyOrder(
                symbol=ticker,
                side=OrderSide.SELL,
                quantity=sell_qty,
                price=0.0,
                order_type=ORDER_TYPE_US_LIMIT,
                reason=f"VA Sell Day {day_count} (Target: {daily_target_amount:.2f})",
            )

    return None


def _calculate_ticker_orders(
    ticker: str,
    config: Dict,
    portfolio: Dict,
    current_prices: Dict[str, float],
    history_data: List[Dict],
    today_date: str,
) -> Tuple[List[StrategyOrder], Optional[Dict]]:
    if not config.get('enabled', True):
        return [], None

    daily_budget = config.get('daily_budget', 0)
    target_cap = config.get('target', 0)
    threshold_rate = config.get('threshold_rate', 0.15)

    holding = portfolio.get(ticker, {})
    cur_price = resolve_current_price(ticker, holding, current_prices)

    current_val = _current_value(holding)
    ticker_hist_entry, ticker_hist_date = _find_ticker_history(ticker, history_data)
    day_count, using_existing_today = _resolve_day_count(
        ticker_hist_entry,
        ticker_hist_date,
        today_date,
    )
    executed_today = _already_executed_today(ticker_hist_entry, using_existing_today)

    target_value_accumulated = _target_value(day_count, daily_budget, target_cap)
    daily_target_amount = target_value_accumulated - current_val
    divergence = _divergence_rate(daily_target_amount, target_value_accumulated)
    avg_price = float(holding.get('avg_price', 0.0))

    context = _build_context(
        day_count,
        daily_budget,
        target_value_accumulated,
        current_val,
        daily_target_amount,
        divergence,
        threshold_rate,
        executed_today,
        cur_price,
        avg_price,
    )

    orders: List[StrategyOrder] = []
    if not executed_today and cur_price > 0 and divergence >= threshold_rate:
        order = _build_order(ticker, day_count, cur_price, daily_target_amount)
        if order:
            orders.append(order)

    return orders, context


def calculate_orders(
    targets_config: Dict,
    portfolio: Dict,
    current_prices: Dict[str, float],
    history_data: List[Dict],
    today_date: str  # YYYY-MM-DD (US Eastern Time expected)
) -> Tuple[List[StrategyOrder], Dict[str, Dict]]:
    """
    Calculate buy/sell orders based on Value Averaging strategy.
    Pure calculation — no market status checks.

    Args:
        targets_config: Configuration for each target ticker.
        portfolio: Current holdings data.
        current_prices: Current market price for each ticker.
        history_data: Loaded history list from JSON.
        today_date: The date string to use for history checks.

    Returns:
        Tuple[List[StrategyOrder], Dict[str, Dict]]:
            1. List of orders to be executed.
            2. Context dictionary for each ticker.
    """
    orders: List[StrategyOrder] = []
    context_map: Dict[str, Dict] = {}

    if not targets_config:
        logging.warning("VA: No targets configured.")
        return orders, context_map

    for ticker, config in targets_config.items():
        ticker_orders, context = _calculate_ticker_orders(
            ticker,
            config,
            portfolio,
            current_prices,
            history_data,
            today_date,
        )
        if context is None:
            continue
        orders.extend(ticker_orders)
        context_map[ticker] = context

    return orders, context_map
