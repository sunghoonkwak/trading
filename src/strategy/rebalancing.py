# -*- coding: utf-8 -*-
"""
Rebalancing Strategy Module

This module implements the static weight rebalancing logic.
It calculates orders to bring assets back to their target weights.
"""
import logging
from typing import Dict, List, Optional, Tuple
from strategy.base import StrategyOrder, OrderSide
from utils.price_utils import resolve_current_price


def _initial_info(seed: float) -> Dict:
    return {
        "orderable_usd": 0.0,
        "total_available": 0.0,
        "total_buy_required": 0.0,
        "scale_factor": 1.0,
        "seed": seed,
        "asset_status": {},
    }


def _collect_asset_data(
    assets: List[Dict],
    portfolio: Dict,
    current_prices: Dict[str, float],
    info: Dict,
) -> Tuple[Optional[Dict], float]:
    asset_data = {}
    total_current_val_in_group = 0.0

    for asset in assets:
        ticker = asset["ticker"]
        holding = portfolio.get(ticker, {})
        cur_price = resolve_current_price(ticker, holding, current_prices)

        if cur_price <= 0:
            logging.warning(f"Rebalancing: No price for {ticker}. Skipping.")
            return None, total_current_val_in_group

        qty = float(holding.get("qty", 0.0))
        current_val = qty * cur_price
        total_current_val_in_group += current_val
        avg_price = float(holding.get("avg_price", 0.0))

        asset_data[ticker] = {
            "target_weight": asset["target_weight"],
            "current_value": current_val,
            "qty": qty,
            "cur_price": cur_price,
        }

        info["asset_status"][ticker] = {
            "qty": qty,
            "cur_val": round(current_val, 2),
            "cur_price": cur_price,
            "avg_price": avg_price,
        }

    return asset_data, total_current_val_in_group


def _available_usd(orderable_usd: float, reserved_cash: float) -> float:
    available_usd = max(0, float(orderable_usd) - reserved_cash)
    if reserved_cash > 0:
        logging.info(
            f"Rebalancing: Orderable USD ${orderable_usd:.2f} "
            f"- reserved ${reserved_cash:.2f} = ${available_usd:.2f}"
        )
    return available_usd


def _add_weight_info(info: Dict, asset_data: Dict, total_current_val_in_group: float) -> None:
    for ticker, data in asset_data.items():
        if total_current_val_in_group > 0:
            cur_w = (data["current_value"] / total_current_val_in_group) * 100
        else:
            cur_w = 0.0

        target_w = data["target_weight"] * 100
        diff_w = cur_w - target_w

        if ticker in info["asset_status"]:
            info["asset_status"][ticker].update({
                "cur_w": round(cur_w, 2),
                "diff_w": round(diff_w, 2),
                "target_w": round(target_w, 2),
            })


def _needs_rebalance(
    asset_data: Dict,
    target_base: float,
    total_current_val_in_group: float,
    threshold: float,
) -> bool:
    available_for_buy = target_base - total_current_val_in_group
    if available_for_buy > 0:
        for ticker, data in asset_data.items():
            target_val = target_base * data["target_weight"]
            if data["current_value"] < target_val and available_for_buy >= data["cur_price"]:
                logging.info(f"Rebalancing trigger: Can buy underweight {ticker} with ${available_for_buy:.2f} cash")
                return True

    if total_current_val_in_group > 0:
        weights = [
            data["current_value"] / total_current_val_in_group
            for data in asset_data.values()
        ]
        weight_spread = max(weights) - min(weights)
        if weight_spread > threshold:
            logging.info(f"Rebalancing trigger: Weight spread {weight_spread:.2%} > threshold {threshold:.2%}")
            return True

    return False


def _build_rebalance_orders(
    asset_data: Dict,
    target_base: float,
) -> Tuple[List[StrategyOrder], float]:
    orders: List[StrategyOrder] = []
    total_buy_required = 0.0

    for ticker, data in asset_data.items():
        target_val = target_base * data["target_weight"]
        diff_val = target_val - data["current_value"]

        if diff_val < 0:
            sell_qty = int(abs(diff_val) / data["cur_price"])
            if sell_qty > 0:
                price = round(data["cur_price"] - 0.01, 2)
                expected_total = (data["qty"] - sell_qty) * data["cur_price"]
                pct = (expected_total / target_base * 100) if target_base > 0 else 0
                orders.append(StrategyOrder(
                    symbol=ticker,
                    side=OrderSide.SELL,
                    quantity=sell_qty,
                    price=price,
                    order_type="00",
                    reason=f"➔ Est.Total: ${expected_total:,.1f} ({pct:.1f}%)",
                ))
        elif diff_val > 0:
            buy_qty = int(diff_val / (data["cur_price"] + 0.01))
            if buy_qty > 0:
                price = round(data["cur_price"] + 0.01, 2)
                total_buy_required += buy_qty * price
                expected_total = (data["qty"] + buy_qty) * data["cur_price"]
                pct = (expected_total / target_base * 100) if target_base > 0 else 0
                orders.append(StrategyOrder(
                    symbol=ticker,
                    side=OrderSide.BUY,
                    quantity=buy_qty,
                    price=price,
                    order_type="00",
                    reason=f"➔ Est.Total: ${expected_total:,.1f} ({pct:.1f}%)",
                ))

    return orders, total_buy_required


def calculate_orders(
    config: Dict,
    portfolio: Dict,
    current_prices: Dict[str, float],
    reserved_cash: float = 0.0,
    orderable_usd: float = 0.0
) -> Tuple[List[StrategyOrder], Dict]:
    """
    Calculate buy/sell orders based on fixed weight rebalancing with a Seed cap.
    Pure calculation — no market status checks.
    Returns: (orders_list, info_dict)
    """
    orders: List[StrategyOrder] = []

    seed = float(config.get("seed", 0))
    assets = config.get("assets", [])
    info = _initial_info(seed)

    if not assets or seed <= 0:
        logging.warning("Rebalancing: Invalid assets or seed.")
        return orders, info

    threshold = config.get("rebalance_threshold", 0.05)

    # 1. Collect current holdings and prices for the rebalancing group.
    asset_data, total_current_val_in_group = _collect_asset_data(
        assets,
        portfolio,
        current_prices,
        info,
    )
    if asset_data is None:
        return [], info

    # 2. Determine the investable target base.
    # Buying power comes from inquire_psamount, not portfolio cash holdings.
    available_usd = _available_usd(orderable_usd, reserved_cash)
    info["orderable_usd"] = float(orderable_usd)

    total_potential_val = total_current_val_in_group + available_usd
    # Aim for the configured seed, capped by holdings plus buying power.
    target_base = min(seed, total_potential_val)

    logging.info(f"Rebalancing: Total Group Value: ${total_potential_val:.2f}, Target Base: ${target_base:.2f}")

    # Populate current/target weight details for reporting.
    _add_weight_info(info, asset_data, total_current_val_in_group)

    # 3. Skip trading when drift is still within the threshold.
    if not _needs_rebalance(asset_data, target_base, total_current_val_in_group, threshold):
        return [], info

    # 4. Build buy orders needed to move back toward target weights.
    orders, total_buy_required = _build_rebalance_orders(asset_data, target_base)

    info["total_available"] = available_usd
    info["total_buy_required"] = total_buy_required

    # We return the orders even if not allowed, so they can be shown in reports.
    # The execution service will check is_allowed before placing them.
    return orders, info
