# -*- coding: utf-8 -*-
"""
Data Service Module (Refactored)

This module provides centralized data access for the application.
It separates data fetching, caching, and transformation logic.
"""
from typing import Dict, List, Tuple

from application.portfolio_service import PortfolioService
from broker import market_data
from data.config_manager import ConfigFile, load_json
from domain.portfolio.processing import PortfolioProcessor  # noqa: F401 - legacy export
from infrastructure.portfolio import build_portfolio_service
from state.system_state import is_kis_ready  # noqa: F401 - legacy patch seam
from utils.market_utils import get_fear_and_greed

# =============================================================================
# Main Service Functions
# =============================================================================

def get_portfolio_data(force_refresh: bool = False, scope: str = "all") -> Dict:
    return build_portfolio_service().get_portfolio_data(
        force_refresh=force_refresh,
        scope=scope,
    )


def _apply_scope_filter(data: Dict, scope: str) -> Dict:
    """Compatibility seam for existing callers and monkeypatch targets."""
    return PortfolioService.apply_scope_filter(data, scope)

def get_weight_diffs(scope: str = "all") -> Tuple[List[Dict], float, Dict]:
    """Calculates rebalancing differences."""
    portfolio = get_portfolio_data(scope=scope)
    merged = portfolio.get("merged_data", {})
    total_usd = portfolio.get("total_value_usd", 0.0)
    targets = portfolio.get("targets", {})
    ex_rate = portfolio.get("exchange_rate", 1.0)

    # 1. Merge configured group constituents into their main tickers.
    try:
        cfg = load_json(ConfigFile.PORTFOLIO_WEIGHTS)
        items = cfg.get('core', []) + cfg.get('satellites', [])
        group_items = [
            item
            for item in items
            if item.get('type') == 'group'
        ]
        group_map = {item['main_ticker']: item.get('constituents', []) for item in group_items}
        group_names = {item['main_ticker']: item.get('name', item['main_ticker']) for item in group_items}
        cash_like_groups = {
            item['main_ticker']
            for item in group_items
            if item.get('name') == 'Bonds'
        }
        constituents = {c for sublist in group_map.values() for c in sublist}
    except:
        group_map, group_names, cash_like_groups, constituents = {}, {}, set(), set()

    cur_weights = dict(portfolio.get("current_weights", {}))
    group_values = {}
    for main, subs in group_map.items():
        group_value = merged.get(main, {}).get("current_value_usd", 0.0)
        for s in subs:
            group_value += merged.get(s, {}).get("current_value_usd", 0.0)
            if s in cur_weights:
                cur_weights[main] = cur_weights.get(main, 0.0) + cur_weights.pop(s, 0.0)
        group_values[main] = group_value

    # 2. Calculate target gaps and approximate order quantities.
    diffs = []
    excluded_tickers = constituents | cash_like_groups
    all_tickers = (set(cur_weights.keys()) | set(targets.keys())) - excluded_tickers

    for t in all_tickers:
        if "cash" in t.lower(): continue

        cur_w, tgt_w = cur_weights.get(t, 0.0), targets.get(t, 0.0)
        diff = tgt_w - cur_w
        data = merged.get(t, {})
        is_group = t in group_map

        # Quantity calculation
        price = data.get("cur_price", 0.0)
        if price <= 0:
            price = market_data.fetch_price(t)

        qty_diff = 0
        if price > 0:
            val_diff_native = (diff * total_usd) * (ex_rate if data.get("currency") == "KRW" else 1.0)
            raw_qty_diff = val_diff_native / price
            epsilon = 1e-9 if raw_qty_diff >= 0 else -1e-9
            qty_diff = int(raw_qty_diff + epsilon)

        diffs.append({
            "ticker": t,
            "name": group_names.get(t, data.get("name", t)),
            "cur_w": cur_w,
            "tgt_w": tgt_w,
            "diff": diff,
            "abs_diff": abs(diff),
            "qty_diff": qty_diff,
            "is_group": is_group,
            "current_value_usd": group_values.get(t, data.get("current_value_usd", 0.0)),
            "target_value_usd": tgt_w * total_usd,
        })

    diffs.sort(key=lambda x: x["abs_diff"], reverse=True)

    # 3. Return current and target cash weights with the diffs.
    current_cash = sum(d["current_value_usd"] for d in merged.values() if d["type"] == "CASH")
    current_cash += sum(group_values.get(main, 0.0) for main in cash_like_groups)
    target_cash = 0.1
    try:
        from data.calculate_weights import get_cash_weight
        target_cash = get_cash_weight(get_fear_and_greed(), cfg.get('cash_strategy', {}))
    except: pass

    return diffs, total_usd, {"current": current_cash/total_usd if total_usd > 0 else 0, "target": target_cash}

def invalidate_cache():
    from infrastructure.portfolio import invalidate_gsheet_cache

    invalidate_gsheet_cache()
