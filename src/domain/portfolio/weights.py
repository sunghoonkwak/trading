"""Pure portfolio allocation and rebalancing rules."""


def _iter_allocation_items(config: dict) -> list:
    return config.get("core", []) + config.get("satellites", [])


def _item_target_ticker(item: dict) -> str:
    return item["main_ticker"] if item.get("type") == "group" else item["ticker"]


def _is_cash_like_bonds_group(item: dict) -> bool:
    return item.get("type") == "group" and item.get("name") == "Bonds"


def _add_item_target(target_weights: dict, item: dict, target_weight: float) -> None:
    if _is_cash_like_bonds_group(item):
        return
    if item.get("type") == "strategy" and item.get("strategy") == "weighted_split":
        constituents = item.get("constituents", [])
        total = sum(constituent.get("weight", 0) for constituent in constituents)
        if total > 0:
            for constituent in constituents:
                ticker = constituent["ticker"]
                target_weights[ticker] = target_weights.get(ticker, 0.0) + (
                    target_weight * constituent.get("weight", 0) / total
                )
        return
    ticker = _item_target_ticker(item)
    target_weights[ticker] = target_weights.get(ticker, 0.0) + target_weight


def get_cash_weight(fear_greed_index: float, cash_strategy: dict) -> float:
    if fear_greed_index <= 20:
        return cash_strategy["min"]
    if fear_greed_index > 80:
        return cash_strategy["max"]
    return cash_strategy["mid"]


def calculate_target_weights(current_weights: dict, config: dict, fear_greed_index: float = 50.0) -> tuple:
    cash_weight = get_cash_weight(
        fear_greed_index,
        config.get("cash_strategy", {"min": 0.10, "mid": 0.20, "max": 0.30}),
    )
    leverage_allocation = {"SOXL": 0.05, "TQQQ": 0.05} if fear_greed_index <= 20 else {}
    stock_total = 1.0 - cash_weight - sum(leverage_allocation.values())
    core_items = config.get("core", [])
    satellite_items = config.get("satellites", [])
    core_score = sum(item["score"] for item in core_items)
    satellite_scores = [
        0.0 if _is_cash_like_bonds_group(item) else item.get("ratio", 0.0) * core_score
        for item in satellite_items
    ]
    total_score = core_score + sum(satellite_scores)
    if total_score == 0:
        return {}, 0, cash_weight
    target_weights: dict[str, float] = {}
    for item in core_items:
        _add_item_target(target_weights, item, item["score"] / total_score * stock_total)
    for item, score in zip(satellite_items, satellite_scores, strict=True):
        _add_item_target(target_weights, item, score / total_score * stock_total)
    for ticker, weight in leverage_allocation.items():
        target_weights[ticker] = target_weights.get(ticker, 0.0) + weight
    return target_weights, total_score, cash_weight


def calculate_current_group_weights(current_weights: dict, config: dict) -> dict:
    merged_weights = dict(current_weights)
    for group in _iter_allocation_items(config):
        if group.get("type") != "group":
            continue
        main_ticker = group["main_ticker"]
        constituent_total = 0.0
        for constituent in group.get("constituents", []):
            if constituent in merged_weights:
                constituent_total += merged_weights.pop(constituent)
        merged_weights[main_ticker] = merged_weights.get(main_ticker, 0.0) + constituent_total
    return merged_weights


def calculate_rebalancing(current_weights: dict, config: dict, fear_greed_index: float = 50.0) -> dict:
    target_weights, _, _ = calculate_target_weights(current_weights, config, fear_greed_index)
    merged_current = calculate_current_group_weights(current_weights, config)
    return {
        ticker: {
            "target": target_weights.get(ticker, 0.0),
            "current": merged_current.get(ticker, 0.0),
            "diff": target_weights.get(ticker, 0.0) - merged_current.get(ticker, 0.0),
        }
        for ticker in set(target_weights) | set(merged_current)
    }
