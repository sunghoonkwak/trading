"""Portfolio-weight calculation adapter used by Telegram composition."""
from typing import Dict, List, Tuple

from broker import market_data
from data.calculate_weights import get_cash_weight
from data.config_manager import ConfigFile, load_json
from infrastructure.portfolio.composition import build_portfolio_service
from utils.market_utils import get_fear_and_greed


def get_portfolio_data(force_refresh: bool = False, scope: str = "all") -> Dict:
    return build_portfolio_service().get_portfolio_data(
        force_refresh=force_refresh,
        scope=scope,
    )


def get_weight_diffs(scope: str = "all") -> Tuple[List[Dict], float, Dict]:
    """Calculate group-aware portfolio weight differences."""
    portfolio = get_portfolio_data(scope=scope)
    merged = portfolio.get("merged_data", {})
    total_usd = portfolio.get("total_value_usd", 0.0)
    targets = portfolio.get("targets", {})
    ex_rate = portfolio.get("exchange_rate", 1.0)
    try:
        config = load_json(ConfigFile.PORTFOLIO_WEIGHTS)
        items = config.get("core", []) + config.get("satellites", [])
        groups = [item for item in items if item.get("type") == "group"]
        group_map = {item["main_ticker"]: item.get("constituents", []) for item in groups}
        group_names = {item["main_ticker"]: item.get("name", item["main_ticker"]) for item in groups}
        cash_groups = {item["main_ticker"] for item in groups if item.get("name") == "Bonds"}
        constituents = {ticker for group in group_map.values() for ticker in group}
    except Exception:
        config, group_map, group_names, cash_groups, constituents = {}, {}, {}, set(), set()

    current_weights = dict(portfolio.get("current_weights", {}))
    group_values = {}
    for main_ticker, members in group_map.items():
        group_value = merged.get(main_ticker, {}).get("current_value_usd", 0.0)
        for ticker in members:
            group_value += merged.get(ticker, {}).get("current_value_usd", 0.0)
            if ticker in current_weights:
                current_weights[main_ticker] = current_weights.get(main_ticker, 0.0) + current_weights.pop(ticker)
        group_values[main_ticker] = group_value

    diffs = []
    tickers = (set(current_weights) | set(targets)) - constituents - cash_groups
    for ticker in tickers:
        if "cash" in ticker.lower():
            continue
        current_weight = current_weights.get(ticker, 0.0)
        target_weight = targets.get(ticker, 0.0)
        difference = target_weight - current_weight
        holding = merged.get(ticker, {})
        price = holding.get("cur_price", 0.0) or market_data.fetch_price(ticker)
        quantity_difference = 0
        if price > 0:
            native_value = difference * total_usd
            if holding.get("currency") == "KRW":
                native_value *= ex_rate
            quantity_difference = int(native_value / price + (1e-9 if native_value >= 0 else -1e-9))
        diffs.append({
            "ticker": ticker,
            "name": group_names.get(ticker, holding.get("name", ticker)),
            "cur_w": current_weight,
            "tgt_w": target_weight,
            "diff": difference,
            "abs_diff": abs(difference),
            "qty_diff": quantity_difference,
            "is_group": ticker in group_map,
            "current_value_usd": group_values.get(ticker, holding.get("current_value_usd", 0.0)),
            "target_value_usd": target_weight * total_usd,
        })
    diffs.sort(key=lambda item: item["abs_diff"], reverse=True)
    current_cash = sum(item["current_value_usd"] for item in merged.values() if item["type"] == "CASH")
    current_cash += sum(group_values.get(ticker, 0.0) for ticker in cash_groups)
    target_cash = get_cash_weight(get_fear_and_greed(), config.get("cash_strategy", {}))
    return diffs, total_usd, {
        "current": current_cash / total_usd if total_usd > 0 else 0,
        "target": target_cash,
    }
