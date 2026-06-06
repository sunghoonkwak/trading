# -*- coding: utf-8 -*-
"""
RAOEO Infinite Buying Method Module (Refactored)

This module implements the "Raoeo Infinite Buying Method" logic.
It dynamically parses the "phase" array rules provided in the configuration.
It is a pure calculation module without direct API dependencies.
"""
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import math

from strategy.base import StrategyOrder, OrderSide
from utils.price_utils import resolve_current_price
from core.constants import ORDER_TYPE_US_LOC, ORDER_TYPE_US_LIMIT

# KIS rejects buy orders exceeding 30% above current price.
# Use 25% cap as a safety margin.
MAX_BUY_PRICE_RATIO = 1.25
_BUDGETED_BUY_REASONS = {"Buy Normal", "Buy Average"}


def _cap_buy_price(price: float, cur_price: float) -> float:
    """Cap buy price to prevent KIS order rejection (30% limit)."""
    max_price = round(cur_price * MAX_BUY_PRICE_RATIO, 2)
    if price > max_price:
        logging.info(f"[RAOEO] Buy price capped: {price:.2f} -> {max_price:.2f} (cur: {cur_price:.2f})")
        return max_price
    return price


def _validate_phase_config(ticker: str, phases: List[Dict]) -> None:
    """
    Validate JSON phases to prevent absurd, destructive inputs.
    Raises ValueError to be intercepted by global Telegram alert dispatchers.
    """
    for p in phases:
        buy_rules = p.get("buy", [])
        sell_rules = p.get("sell", [])

        if not isinstance(buy_rules, list) or not isinstance(sell_rules, list):
            raise ValueError(f"[{ticker}] Invalid Phase: 'buy' and 'sell' must be lists in phase '{p.get('name', 'Unknown')}'.")

        for r in buy_rules:
            ratio = float(r.get("ratio", 1.0))
            b_type = r.get("type", "normal")
            if ratio < 0.0 or ratio > 2.0:
                raise ValueError(f"[{ticker}] Absurd buy ratio: {ratio} in type '{b_type}'. Allowed: 0.0 ~ 2.0.")
            if b_type not in ("normal", "average", "filling"):
                raise ValueError(f"[{ticker}] Unknown buy type '{b_type}'.")

        for r in sell_rules:
            ratio = float(r.get("ratio", 0.0))
            profit = float(r.get("profit", 0.0))
            if ratio < 0.0 or ratio > 2.0:
                raise ValueError(f"[{ticker}] Absurd sell ratio: {ratio}. Allowed: 0.0 ~ 2.0")
            if profit < 0.0 or profit > 0.5:
                raise ValueError(f"[{ticker}] Absurd sell profit: {profit} ({profit*100}%). Allowed: 0.0 ~ 0.50 (50%).")


def _budget_carryover_by_reason(
    ticker: str,
    history_data: Optional[List[Dict]],
    today_date: Optional[str],
) -> Dict[str, float]:
    """Return unused previous RAOEO buy budget by buy reason."""
    if not history_data:
        return {}

    for entry in history_data:
        if today_date and entry.get("date") == today_date:
            continue

        orders = entry.get("raoeo", {}).get("orders", [])
        carryovers: Dict[str, float] = {}
        for order in orders:
            if order.get("ticker") != ticker:
                continue
            if order.get("side") != OrderSide.BUY.name:
                continue
            if not order.get("success", False):
                continue

            reason = order.get("reason", "")
            if reason not in _BUDGETED_BUY_REASONS:
                continue

            target_budget = order.get("target_budget")
            if target_budget is None:
                continue

            ordered_notional = float(order.get("qty", 0)) * float(order.get("price", 0.0))
            unused_budget = max(0.0, float(target_budget) - ordered_notional)
            carryovers[reason] = round(carryovers.get(reason, 0.0) + unused_budget, 2)

        if carryovers:
            return carryovers

    return {}


def _is_rule_disabled(rule: Dict) -> bool:
    return str(rule.get("disable", "false")).lower() == "true"


def _select_phase(phases: List[Dict], progress_ratio: float) -> Dict:
    matched_phase = phases[-1]
    for phase in phases:
        if "threshold" in phase and progress_ratio < phase["threshold"]:
            return phase
    return matched_phase


def _build_sell_orders(
    ticker: str,
    qty: int,
    avg_price: float,
    sell_rules: List[Dict],
) -> List[StrategyOrder]:
    if qty <= 0 or avg_price <= 0:
        return []

    orders: List[StrategyOrder] = []
    remaining_ratio = sum(
        rule.get("ratio", 0.0)
        for rule in sell_rules
        if not _is_rule_disabled(rule)
    )
    remaining_sell_qty = int(qty * remaining_ratio)

    for i, sell_rule in enumerate(sell_rules):
        if _is_rule_disabled(sell_rule):
            continue

        profit = float(sell_rule.get("profit", 0.0))
        ratio = float(sell_rule.get("ratio", 0.0))
        target_sell_price = round(avg_price * (1 + profit), 2)

        rule_qty = int(qty * ratio)
        if i == len(sell_rules) - 1:
            rule_qty = remaining_sell_qty

        if rule_qty > 0:
            order_type_str = sell_rule.get("type", "Limit")
            order_type = ORDER_TYPE_US_LOC if order_type_str == "LOC" else ORDER_TYPE_US_LIMIT

            orders.append(StrategyOrder(
                symbol=ticker,
                side=OrderSide.SELL,
                quantity=rule_qty,
                price=target_sell_price,
                order_type=order_type,
                reason=f"Sell {order_type_str} {int(profit*100)}% profit"
            ))

        remaining_sell_qty -= rule_qty

    return orders


def _min_active_sell_profit(sell_rules: List[Dict]) -> float:
    active_sell_rules = [
        rule for rule in sell_rules
        if not _is_rule_disabled(rule)
    ]
    if not active_sell_rules:
        return 0.1
    return min(float(rule.get("profit", 0.0)) for rule in active_sell_rules)


def _buy_price_for_rule(
    buy_rule: Dict,
    base_price: float,
    cur_price: float,
    min_profit: float,
) -> float:
    price_percent_cap = float(buy_rule.get("price_percent_cap", float("inf")))
    target_buy_px = round((min(price_percent_cap, min_profit) + 1) * base_price - 0.01, 2)
    return _cap_buy_price(target_buy_px, cur_price)


def _build_buy_orders(
    ticker: str,
    qty: int,
    seed: float,
    daily_budget: float,
    base_price: float,
    cur_price: float,
    buy_rules: List[Dict],
    sell_rules: List[Dict],
    budget_carryovers: Dict[str, float],
) -> List[StrategyOrder]:
    orders: List[StrategyOrder] = []
    buy_qty_main = 0
    min_profit = _min_active_sell_profit(sell_rules)

    for buy_rule in buy_rules:
        if _is_rule_disabled(buy_rule):
            continue

        buy_type = buy_rule.get("type", "normal")
        buy_price = _buy_price_for_rule(buy_rule, base_price, cur_price, min_profit)

        if buy_type in ("normal", "average"):
            buy_reason = "Buy Normal" if buy_type == "normal" else "Buy Average"
            buy_ratio = float(buy_rule.get("ratio", 1.0))
            alloc_budget = round(
                daily_budget * buy_ratio + budget_carryovers.get(buy_reason, 0.0),
                2,
            )
            rule_qty = max(1, int(alloc_budget / buy_price))
            buy_qty_main += rule_qty
            orders.append(StrategyOrder(
                symbol=ticker, side=OrderSide.BUY, quantity=rule_qty,
                price=buy_price, order_type=ORDER_TYPE_US_LOC, reason=buy_reason,
                target_budget=alloc_budget,
            ))

        elif buy_type == "filling":
            target_ratio = float(buy_rule.get("target_ratio", 0.1))
            target_seed_qty = int((seed * target_ratio) / base_price)
            rem_qty = target_seed_qty - qty - buy_qty_main
            if rem_qty > 0:
                orders.append(StrategyOrder(
                    symbol=ticker, side=OrderSide.BUY, quantity=rem_qty,
                    price=buy_price, order_type=ORDER_TYPE_US_LOC, reason="Buy Filling"
                ))

    return orders


def _calculate_ticker_orders(
    ticker: str,
    config: Dict,
    portfolio: Dict,
    current_prices: Dict[str, float],
    history_data: Optional[List[Dict]],
    today_date: Optional[str],
) -> Tuple[List[StrategyOrder], Optional[Dict]]:
    if 'seed' not in config or 'duration' not in config:
        logging.error(f"RAOEO: Missing config for {ticker}")
        return [], None

    phases = config.get("phase", [])
    if not phases:
        logging.warning(f"RAOEO: No phase configuration found for {ticker}. Skipping.")
        return [], None

    _validate_phase_config(ticker, phases)

    seed = float(config['seed'])
    duration = int(config['duration'])
    if seed <= 0 or duration <= 0:
        raise ValueError(f"[{ticker}] Invalid config: seed and duration must be positive (seed={seed}, duration={duration}).")

    holding = portfolio.get(ticker, {})
    qty = int(holding.get('qty', 0))
    avg_price = float(holding.get('avg_price', 0.0))

    cur_price = resolve_current_price(ticker, holding, current_prices)
    if cur_price <= 0:
        logging.warning(f"RAOEO: No price for {ticker}. Skipping.")
        return [], None

    daily_budget = seed / duration
    spent_amount = avg_price * qty
    progress_ratio = spent_amount / seed if seed > 0 else 0.0
    base_price = avg_price if avg_price > 0 else cur_price

    matched_phase = _select_phase(phases, progress_ratio)
    phase_name = matched_phase.get("name", "Unknown Phase")
    sell_rules = matched_phase.get("sell", [])
    buy_rules = matched_phase.get("buy", [])
    budget_carryovers = _budget_carryover_by_reason(ticker, history_data, today_date)

    ticker_orders = _build_sell_orders(ticker, qty, avg_price, sell_rules)
    ticker_orders.extend(_build_buy_orders(
        ticker=ticker,
        qty=qty,
        seed=seed,
        daily_budget=daily_budget,
        base_price=base_price,
        cur_price=cur_price,
        buy_rules=buy_rules,
        sell_rules=sell_rules,
        budget_carryovers=budget_carryovers,
    ))

    buy_orders = [order for order in ticker_orders if order.side == OrderSide.BUY]
    sell_orders = [order for order in ticker_orders if order.side == OrderSide.SELL]
    logging.info(
        f"[RAOEO] {ticker:<5} | {phase_name:<20} | "
        f"Hold: {spent_amount:8.2f} / {seed:8.2f} ({progress_ratio*100:5.1f}%) | "
        f"Orders: Buyx{len(buy_orders)}, Sellx{len(sell_orders)}"
    )

    return ticker_orders, {
        "phase": phase_name,
        "spent": spent_amount,
        "seed": seed,
        "progress_pct": progress_ratio * 100,
        "cur_price": cur_price,
        "avg_price": avg_price,
        "budget_carryover": round(sum(budget_carryovers.values()), 2),
    }


def calculate_cash_funding_order(
    orders: List[StrategyOrder],
    portfolio: Dict,
    current_prices: Dict[str, float],
    cash_ticker: str,
    orderable_usd: float,
) -> Tuple[Optional[StrategyOrder], Dict]:
    """Build an approved cash-ticker sale using KIS orderable USD."""
    total_buy_budget = sum(
        order.price * order.quantity
        for order in orders
        if order.side == OrderSide.BUY
    )
    shortfall = round(max(0.0, total_buy_budget - orderable_usd), 2)
    info = {
        "buy_budget": total_buy_budget,
        "orderable_usd": orderable_usd,
        "shortfall": shortfall,
        "required": shortfall > 0,
        "error": None,
    }

    if shortfall <= 0:
        return None, info
    if not cash_ticker:
        info["error"] = "cash_ticker is not configured."
        return None, info

    cash_holding = portfolio.get(cash_ticker, {})
    cash_cur_price = resolve_current_price(cash_ticker, cash_holding, current_prices)
    if cash_cur_price <= 0:
        info["error"] = f"Could not find price for cash_ticker {cash_ticker}."
        return None, info

    sell_price = round(cash_cur_price * 0.99, 2)
    required_qty = math.ceil(shortfall / sell_price)
    holding_qty = int(portfolio.get(cash_ticker, {}).get("qty", 0))
    if holding_qty < required_qty:
        info["error"] = (
            f"Insufficient {cash_ticker} holding for cash funding "
            f"(required: {required_qty}, holding: {holding_qty})."
        )
        return None, info

    order = StrategyOrder(
        symbol=cash_ticker,
        side=OrderSide.SELL,
        quantity=required_qty,
        price=sell_price,
        order_type=ORDER_TYPE_US_LIMIT,
        reason=(
            f"Fund RAOEO Buys "
            f"(Buy: ${total_buy_budget:.2f}, Orderable USD: ${orderable_usd:.2f}, "
            f"Shortfall: ${shortfall:.2f})"
        ),
    )
    return order, info


def calculate_orders(
    targets_config: Dict,
    portfolio: Dict,
    current_prices: Dict[str, float],
    exchange_rates: Optional[Dict[str, float]] = None,
    history_data: Optional[List[Dict]] = None,
    today_date: Optional[str] = None,
) -> Tuple[List[StrategyOrder], Dict]:
    """
    Calculate buy/sell orders based on the dynamic RAOEO phase configuration.
    Pure calculation — no market status checks.

    Args:
        targets_config: Configuration for each target ticker.
        portfolio: Current holdings data.
        current_prices: Current market price for each ticker.
        exchange_rates: Optional currency exchange rates.

    Returns:
        Tuple[List[StrategyOrder], Dict]:
            1. List of orders to be executed.
            2. Info dictionary with ticker metadata.
    """
    orders: List[StrategyOrder] = []
    info = {"ticker_info": {}}

    if not targets_config:
        logging.warning("RAOEO: No targets configured.")
        return orders, info

    for ticker, config in targets_config.items():
        ticker_orders, ticker_info = _calculate_ticker_orders(
            ticker,
            config,
            portfolio,
            current_prices,
            history_data,
            today_date,
        )
        if ticker_info is None:
            continue
        orders.extend(ticker_orders)
        info["ticker_info"][ticker] = ticker_info

    return orders, info
