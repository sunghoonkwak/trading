# -*- coding: utf-8 -*-
"""
Rebalancing Strategy Module

This module implements the static weight rebalancing logic.
It calculates orders to bring assets back to their target weights.
"""
import logging
from typing import Dict, List, Tuple
from strategy.base import StrategyOrder, OrderSide
from constants import ORDER_TYPE_US_LOC

def calculate_orders(
    config: Dict,
    portfolio: Dict,
    current_prices: Dict[str, float]
) -> Tuple[List[StrategyOrder], Dict]:
    """
    Calculate buy/sell orders based on fixed weight rebalancing with a Seed cap.
    Returns: (orders_list, info_dict)
    """
    orders: List[StrategyOrder] = []

    seed = float(config.get("seed", 0))
    assets = config.get("assets", [])

    info = {
        "usd_cash": 0.0,
        "total_available": 0.0,
        "total_buy_required": 0.0,
        "scale_factor": 1.0,
        "seed": seed,
        "asset_status": {}
    }

    if not assets or seed <= 0:
        logging.warning("Rebalancing: Invalid assets or seed.")
        return orders, info

    threshold = config.get("rebalance_threshold", 0.05)

    # 1. Calculate Current State
    asset_data = {}
    total_current_val_in_group = 0.0

    for a in assets:
        ticker = a["ticker"]
        target_w = a["target_weight"]

        holding = portfolio.get(ticker, {})
        cur_price = current_prices.get(ticker, 0.0)
        if cur_price <= 0:
            cur_price = float(holding.get("cur_price", 0.0))

        if cur_price <= 0:
            logging.warning(f"Rebalancing: No price for {ticker}. Skipping.")
            return [], info

        qty = float(holding.get("qty", 0.0))
        current_val = qty * cur_price
        total_current_val_in_group += current_val

        asset_data[ticker] = {
            "target_weight": target_w,
            "current_value": current_val,
            "qty": qty,
            "cur_price": cur_price
        }

        info["asset_status"][ticker] = {
            "qty": qty,
            "cur_val": round(current_val, 2)
        }

    # 2. Determine Real Target Base
    # Total potential value = current stock + current cash
    usd_cash_data = portfolio.get("USD cash", {})
    usd_cash = float(usd_cash_data.get("qty", 0))
    info["usd_cash"] = usd_cash

    total_potential_val = total_current_val_in_group + usd_cash
    # We aim for Seed, but if we have less money, we balance what we have.
    target_base = min(seed, total_potential_val)

    logging.info(f"Rebalancing: Total Group Value: ${total_potential_val:.2f}, Target Base: ${target_base:.2f}")

    # [NEW] Populate Weight Info for Reporting
    for ticker, data in asset_data.items():
        if total_current_val_in_group > 0:
            cur_w = (data["current_value"] / total_current_val_in_group) * 100
        else:
            cur_w = 0.0

        target_w = data["target_weight"] * 100
        diff_w = cur_w - target_w

        # Update info
        if ticker in info["asset_status"]:
            info["asset_status"][ticker].update({
                "cur_w": round(cur_w, 2),
                "diff_w": round(diff_w, 2),
                "target_w": round(target_w, 2)
            })

    # 3. Check Trigger
    needs_rebalance = False

    # Condition 1: Cash available to buy at least 1 share of underweight stock
    available_for_buy = target_base - total_current_val_in_group
    if available_for_buy > 0:
        for ticker, data in asset_data.items():
            target_val = target_base * data["target_weight"]
            if data["current_value"] < target_val and available_for_buy >= data["cur_price"]:
                logging.info(f"Rebalancing trigger: Can buy underweight {ticker} with ${available_for_buy:.2f} cash")
                needs_rebalance = True
                break

    # Condition 2: Weight spread between stocks exceeds threshold
    if not needs_rebalance and total_current_val_in_group > 0:
        weights = [d["current_value"] / total_current_val_in_group for d in asset_data.values()]
        weight_spread = max(weights) - min(weights)
        if weight_spread > threshold:
            logging.info(f"Rebalancing trigger: Weight spread {weight_spread:.2%} > threshold {threshold:.2%}")
            needs_rebalance = True

    if not needs_rebalance:
        return [], info

    # 4. Calculate Balanced Orders
    total_buy_required = 0.0
    for ticker, data in asset_data.items():
        target_val = target_base * data["target_weight"]
        diff_val = target_val - data["current_value"]

        if diff_val < 0:
            # SELL
            sell_qty = int(abs(diff_val) / data["cur_price"])
            if sell_qty > 0:
                expected_total = (data["qty"] - sell_qty) * data["cur_price"]
                pct = (expected_total / target_base * 100) if target_base > 0 else 0
                orders.append(StrategyOrder(
                    symbol=ticker,
                    side=OrderSide.SELL,
                    quantity=sell_qty,
                    price=0.0,
                    order_type="00",
                    reason=f"➔ Est.Total: ${expected_total:,.1f} ({pct:.1f}%)"
                ))
        elif diff_val > 0:
            # BUY (Apply 3% buffer for LOC margin check)
            buy_qty = int(diff_val / (data["cur_price"] * 1.03))
            if buy_qty > 0:
                total_buy_required += (buy_qty * data["cur_price"] * 1.03)
                expected_total = (data["qty"] + buy_qty) * data["cur_price"]
                pct = (expected_total / target_base * 100) if target_base > 0 else 0
                orders.append(StrategyOrder(
                    symbol=ticker,
                    side=OrderSide.BUY,
                    quantity=buy_qty,
                    price=round(data["cur_price"] * 1.03, 2),
                    order_type="34",
                    reason=f"➔ Est.Total: ${expected_total:,.1f} ({pct:.1f}%)"
                ))

    info["total_available"] = usd_cash
    info["total_buy_required"] = total_buy_required

    return orders, info
