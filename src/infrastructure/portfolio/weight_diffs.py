"""Portfolio-weight calculation adapter used by Telegram composition."""
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Tuple


@dataclass(frozen=True)
class WeightDiffDependencies:
    """Concrete collaborators supplied by the composition root."""

    get_portfolio_data: Callable[[str], Dict[str, Any]]
    load_weights: Callable[[], Dict[str, Any]]
    get_cash_weight: Callable[[Any, Dict[str, Any]], float]
    get_fear_and_greed: Callable[[], Any]
    fetch_price: Callable[[str], float]


def get_weight_diffs(
    scope: str,
    dependencies: WeightDiffDependencies,
) -> Tuple[List[Dict], float, Dict]:
    """Calculate group-aware portfolio weight differences."""
    portfolio = dependencies.get_portfolio_data(scope)
    merged = portfolio.get("merged_data", {})
    total_usd = portfolio.get("total_value_usd", 0.0)
    targets = portfolio.get("targets", {})
    ex_rate = portfolio.get("exchange_rate", 1.0)
    try:
        config = dependencies.load_weights()
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
        price = holding.get("cur_price", 0.0) or dependencies.fetch_price(ticker)
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
    target_cash = dependencies.get_cash_weight(
        dependencies.get_fear_and_greed(), config.get("cash_strategy", {})
    )
    return diffs, total_usd, {
        "current": current_cash / total_usd if total_usd > 0 else 0,
        "target": target_cash,
    }
