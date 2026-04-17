# -*- coding: utf-8 -*-
"""
RAOEO Infinite Buying Method Module (Refactored)

This module implements the "Raoeo Infinite Buying Method" logic.
It is now a pure calculation module without direct API dependencies.
"""
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import math

from strategy.base import StrategyOrder, OrderSide
from core.constants import ORDER_TYPE_US_LOC, ORDER_TYPE_US_LIMIT

# Constants removed (moved to constants.py)

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


def calculate_orders(
    targets_config: Dict,
    portfolio: Dict,
    current_prices: Dict[str, float],
    exchange_rates: Optional[Dict[str, float]] = None
) -> Tuple[List[StrategyOrder], Dict]:
    """
    Calculate buy/sell orders based on the RAOEO strategy.
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

        seed = float(config['seed'])
        duration = int(config['duration'])
        sell_profit = float(config.get('sell_profit', 0.10))

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

        # 3. Calculate Daily Budget
        daily_budget = seed / duration
        spent_amount = avg_price * qty
        ten_pct_seed = seed * 0.1
        twenty_pct_seed = seed * 0.2
        half_seed = seed / 2

        if spent_amount < ten_pct_seed:
            phase = "Phase0"
        elif spent_amount < twenty_pct_seed:
            phase = "Phase1"
        elif spent_amount < half_seed:
            phase = "Phase2"
        else:
            phase = "Phase3"

        # ---------------------------------------------------------
        # Logic A: Sell Logic (Sell all if profit target reached)
        # ---------------------------------------------------------
        ticker_orders = []
        if qty > 0 and avg_price > 0:
            if phase in ["Phase0", "Phase1"]:
                profit_margin = sell_profit * 2
            else:
                profit_margin = sell_profit

            sellable_qty = qty
            target_sell_price = round(avg_price * (1 + profit_margin), 2)

            # Split into Limit (50%) and LOC (50%)
            qty_limit = (sellable_qty // 2) + (sellable_qty % 2)
            qty_loc = sellable_qty // 2

            if qty_limit > 0:
                ticker_orders.append(StrategyOrder(
                    symbol=ticker,
                    side=OrderSide.SELL,
                    quantity=qty_limit,
                    price=target_sell_price,
                    order_type=ORDER_TYPE_US_LIMIT,
                    reason=f"Sell Limit {int(profit_margin*100)}% profit"
                ))

            if qty_loc > 0:
                ticker_orders.append(StrategyOrder(
                    symbol=ticker,
                    side=OrderSide.SELL,
                    quantity=qty_loc,
                    price=target_sell_price,
                    order_type=ORDER_TYPE_US_LOC,
                    reason=f"Sell LOC {int(profit_margin*100)}% profit"
                ))

        # ---------------------------------------------------------
        # Logic B: Buy Logic (Phases)
        # ---------------------------------------------------------
        buy_price_main = 0.0
        buy_qty_main = 0

        # Use cur_price as fallback for avg_price (e.g., after full sell)
        base_price = avg_price if avg_price > 0 else cur_price

        # Phase 0: Initial Phase (Holdings < 10% of seed)
        if phase == "Phase0":
            target_sell_price = round(base_price * (1 + sell_profit * 2), 2)
            buy_price_main = target_sell_price - 0.01
            buy_price_main = _cap_buy_price(buy_price_main, cur_price)
            buy_qty_main = int(daily_budget / buy_price_main)
            if buy_qty_main < 1: buy_qty_main = 1

            ticker_orders.append(StrategyOrder(
                symbol=ticker,
                side=OrderSide.BUY,
                quantity=buy_qty_main,
                price=buy_price_main,
                order_type=ORDER_TYPE_US_LOC,
                reason=f"Phase0: Main Buy"
            ))

            # Fill Order: Fill up to 10% of seed
            seed_10pct_qty = int(ten_pct_seed / base_price)
            remaining_fill_qty = seed_10pct_qty - qty - buy_qty_main

            if remaining_fill_qty > 0:
                buy_price_fill = round(base_price * 0.95, 2)
                buy_price_fill = _cap_buy_price(buy_price_fill, cur_price)
                ticker_orders.append(StrategyOrder(
                    symbol=ticker,
                    side=OrderSide.BUY,
                    quantity=remaining_fill_qty,
                    price=buy_price_fill,
                    order_type=ORDER_TYPE_US_LOC,
                    reason=f"Phase0: Fill 10%"
                ))

        # Phase 1: Normal Phase (10% <= Holdings < 20%)
        elif phase == "Phase1":
            target_sell_price = round(base_price * (1 + sell_profit * 2), 2)
            buy_price_main = target_sell_price - 0.01
            buy_price_main = _cap_buy_price(buy_price_main, cur_price)
            buy_qty_main = int(daily_budget / buy_price_main)
            if buy_qty_main < 1: buy_qty_main = 1

            ticker_orders.append(StrategyOrder(
                symbol=ticker,
                side=OrderSide.BUY,
                quantity=buy_qty_main,
                price=buy_price_main,
                order_type=ORDER_TYPE_US_LOC,
                reason="Phase1: Normal Buy"
            ))

        # Phase 2: Normal Phase (20% <= Holdings < 50%)
        elif phase == "Phase2":
            target_sell_price = round(base_price * (1 + sell_profit), 2)
            buy_price_main = target_sell_price - 0.01
            buy_price_main = _cap_buy_price(buy_price_main, cur_price)
            buy_qty_main = int(daily_budget / buy_price_main)
            if buy_qty_main < 1: buy_qty_main = 1

            ticker_orders.append(StrategyOrder(
                symbol=ticker,
                side=OrderSide.BUY,
                quantity=buy_qty_main,
                price=buy_price_main,
                order_type=ORDER_TYPE_US_LOC,
                reason="Phase2: Normal Buy"
            ))

        # Phase 3: Aggressive Phase (Holdings >= 50%)
        else: # Phase3
            # Order 1: 50% of daily budget at base price (avg or cur)
            buy_price_1 = round(base_price, 2)
            buy_price_1 = _cap_buy_price(buy_price_1, cur_price)
            total_buy_qty = int(daily_budget / base_price)
            buy_qty_1 = total_buy_qty // 2
            if buy_qty_1 < 1: buy_qty_1 = 1

            ticker_orders.append(StrategyOrder(
                symbol=ticker,
                side=OrderSide.BUY,
                quantity=buy_qty_1,
                price=buy_price_1,
                order_type=ORDER_TYPE_US_LOC,
                reason=f"Phase3: Avg Buy"
            ))

            # Order 2: 50% of daily budget at target_sell_price - 0.01
            target_sell_price = round(base_price * (1 + sell_profit), 2)
            buy_price_2 = target_sell_price - 0.01
            buy_price_2 = _cap_buy_price(buy_price_2, cur_price)
            buy_qty_2 = max(0, total_buy_qty - buy_qty_1)

            if buy_qty_2 > 0:
                ticker_orders.append(StrategyOrder(
                    symbol=ticker,
                    side=OrderSide.BUY,
                    quantity=buy_qty_2,
                    price=buy_price_2,
                    order_type=ORDER_TYPE_US_LOC,
                    reason=f"Phase3: Upper Buy"
                ))

        orders.extend(ticker_orders)

        # ---------------------------------------------------------
        # Logic C: Logging Summary
        # ---------------------------------------------------------
        buy_orders = [o for o in ticker_orders if o.side == OrderSide.BUY]
        sell_orders = [o for o in ticker_orders if o.side == OrderSide.SELL]

        logging.info(
            f"[RAOEO] {ticker:<5} | {phase} | "
            f"Hold: {spent_amount:8.2f} / {seed:8.2f} ({spent_amount/seed*100:5.1f}%) | "
            f"Orders: Buyx{len(buy_orders)}, Sellx{len(sell_orders)}"
        )

        info["ticker_info"][ticker] = {
            "phase": phase,
            "spent": spent_amount,
            "seed": seed,
            "progress_pct": (spent_amount/seed*100) if seed > 0 else 0,
            "cur_price": cur_price,
            "avg_price": avg_price
        }

    return orders, info
