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
from core.constants import ORDER_TYPE_US_LOC, ORDER_TYPE_US_LIMIT

# KIS rejects buy orders exceeding 30% above current price.
# Use 25% cap as a safety margin.
MAX_BUY_PRICE_RATIO = 1.25


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


# -------------------------------------------------------------
# Buy Strategy Helper Factories
# -------------------------------------------------------------




# -------------------------------------------------------------
# Main Phase Engine Loop
# -------------------------------------------------------------

def calculate_orders(
    targets_config: Dict,
    portfolio: Dict,
    current_prices: Dict[str, float],
    exchange_rates: Optional[Dict[str, float]] = None
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
        # 1. Validate Config
        if 'seed' not in config or 'duration' not in config:
            logging.error(f"RAOEO: Missing config for {ticker}")
            continue

        phases = config.get("phase", [])
        if not phases:
            logging.warning(f"RAOEO: No phase configuration found for {ticker}. Skipping.")
            continue

        # Security: Halt if invalid configurations are supplied
        _validate_phase_config(ticker, phases)

        seed = float(config['seed'])
        duration = int(config['duration'])

        # 2. Get Current Status
        holding = portfolio.get(ticker, {})
        qty = int(holding.get('qty', 0))
        avg_price = float(holding.get('avg_price', 0.0))

        # Current price priority: explicit arg > holding's current price > 0
        cur_price = current_prices.get(ticker, 0.0)
        if cur_price <= 0:
            cur_price = float(holding.get('cur_price', 0.0))

        if cur_price <= 0:
            logging.warning(f"RAOEO: No price for {ticker}. Skipping.")
            continue

        # 3. Calculate Core Metrics
        daily_budget = seed / duration
        spent_amount = avg_price * qty
        progress_ratio = spent_amount / seed if seed > 0 else 0.0

        # Base price falls back to cur_price if avg_price is 0
        base_price = avg_price if avg_price > 0 else cur_price

        # 4. Resolve Dynamic Phase from Config
        matched_phase = phases[-1]  # Fallback to the last phase
        for p in phases:
            if "threshold" in p and progress_ratio < p["threshold"]:
                matched_phase = p
                break

        phase_name = matched_phase.get("name", "Unknown Phase")
        ticker_orders = []

        # 5. Build Sell Logic Paths
        sell_rules = matched_phase.get("sell", [])
        buy_target_sell_prices = []  # Collector for evaluating minimum target limits

        if qty > 0 and avg_price > 0:
            remaining_ratio = sum(r.get("ratio", 0.0) for r in sell_rules)
            total_sell_qty = int(qty * remaining_ratio)
            remaining_sell_qty = total_sell_qty

            for i, sell_rule in enumerate(sell_rules):
                profit = float(sell_rule.get("profit", 0.0))
                ratio = float(sell_rule.get("ratio", 0.0))

                target_sell_price = round(avg_price * (1 + profit), 2)
                buy_target_sell_prices.append(target_sell_price)

                # Rule apportionment
                rule_qty = int(qty * ratio)
                if i == len(sell_rules) - 1:
                    # Last rule handles remaining rounding fragments
                    rule_qty = remaining_sell_qty

                if rule_qty > 0:
                    o_type_str = sell_rule.get("type", "Limit")
                    o_type = ORDER_TYPE_US_LOC if o_type_str == "LOC" else ORDER_TYPE_US_LIMIT

                    ticker_orders.append(StrategyOrder(
                        symbol=ticker,
                        side=OrderSide.SELL,
                        quantity=rule_qty,
                        price=target_sell_price,
                        order_type=o_type,
                        reason=f"Sell {o_type_str} {int(profit*100)}% profit"
                    ))
                remaining_sell_qty -= rule_qty
        else:
            # Ghost sell price calculations for normal buy targeting
            for sell_rule in sell_rules:
                profit = float(sell_rule.get("profit", 0.0))
                target_sell_price = round(base_price * (1 + profit), 2)
                buy_target_sell_prices.append(target_sell_price)

        # 6. Branch into Buy Logic Factories
        buy_rules = matched_phase.get("buy", [])
        min_profit = min([float(r.get("profit", 0.0)) for r in sell_rules]) if sell_rules else 0.1
        buy_qty_main = 0

        for buy_rule in buy_rules:
            b_type = buy_rule.get("type", "normal")

            price_percent_cap = float(buy_rule.get("price_percent_cap", float("inf")))
            target_buy_px = round((min(price_percent_cap, min_profit) + 1) * base_price - 0.01, 2)
            buy_price = _cap_buy_price(target_buy_px, cur_price)

            if b_type == "normal":
                b_ratio = float(buy_rule.get("ratio", 1.0))
                alloc_budget = daily_budget * b_ratio
                rule_qty = max(1, int(alloc_budget / buy_price))
                buy_qty_main += rule_qty
                ticker_orders.append(StrategyOrder(
                    symbol=ticker, side=OrderSide.BUY, quantity=rule_qty,
                    price=buy_price, order_type=ORDER_TYPE_US_LOC, reason="Buy Normal"
                ))

            elif b_type == "average":
                b_ratio = float(buy_rule.get("ratio", 1.0))
                alloc_budget = daily_budget * b_ratio
                rule_qty = max(1, int(alloc_budget / buy_price))
                buy_qty_main += rule_qty
                ticker_orders.append(StrategyOrder(
                    symbol=ticker, side=OrderSide.BUY, quantity=rule_qty,
                    price=buy_price, order_type=ORDER_TYPE_US_LOC, reason="Buy Average"
                ))

            elif b_type == "filling":
                target_ratio = float(buy_rule.get("target_ratio", 0.1))
                target_seed_qty = int((seed * target_ratio) / base_price)
                rem_qty = target_seed_qty - qty - buy_qty_main
                if rem_qty > 0:
                    ticker_orders.append(StrategyOrder(
                        symbol=ticker, side=OrderSide.BUY, quantity=rem_qty,
                        price=buy_price, order_type=ORDER_TYPE_US_LOC, reason="Buy Filling"
                    ))

        orders.extend(ticker_orders)

        # 7. Logging Summary
        buy_orders = [o for o in ticker_orders if o.side == OrderSide.BUY]
        sell_orders = [o for o in ticker_orders if o.side == OrderSide.SELL]

        logging.info(
            f"[RAOEO] {ticker:<5} | {phase_name:<20} | "
            f"Hold: {spent_amount:8.2f} / {seed:8.2f} ({progress_ratio*100:5.1f}%) | "
            f"Orders: Buyx{len(buy_orders)}, Sellx{len(sell_orders)}"
        )

        info["ticker_info"][ticker] = {
            "phase": phase_name,
            "spent": spent_amount,
            "seed": seed,
            "progress_pct": progress_ratio * 100,
            "cur_price": cur_price,
            "avg_price": avg_price
        }

    return orders, info
