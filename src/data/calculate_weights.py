"""
Portfolio Weight Calculation

Allocation logic:
1. Cash allocation based on F&G index:
   - F&G <= 20 (Extreme Fear): min cash (0.1) + leverage 10% (SOXL 5%, TQQQ 5%)
   - 20 < F&G <= 80 (Neutral): mid cash (0.2)
   - F&G > 80 (Extreme Greed): max cash (0.3) - defensive

2. Stock total = 1.0 - cash - leverage_total

3. Core/satellite score-based allocation:
   - Core items use explicit scores
   - Satellite items use ratio * core_score
   - Target weight = (score / total_score) * stock_total

4. Item handling:
   - individual: ticker gets the target
   - group: main_ticker gets the target
   - weighted_split strategy: target is split by constituent weights

5. Group handling:
   - Target: main_ticker gets full group target (constituents don't reduce it)
   - Current: main_ticker's holding + sum of constituents' holdings

6. Leverage allocation (Extreme Fear only):
   - SOXL: 5% fixed
   - TQQQ: 5% fixed
"""

from data.config_manager import ConfigFile, load_json


def _iter_allocation_items(config: dict) -> list:
    return config.get('core', []) + config.get('satellites', [])


def _item_target_ticker(item: dict) -> str:
    if item.get('type') == 'group':
        return item['main_ticker']
    return item['ticker']


def _add_weighted_split_target(target_weights: dict, item: dict, target_weight: float) -> None:
    constituents = item.get('constituents', [])
    total_internal_weight = sum(c.get('weight', 0) for c in constituents)

    if total_internal_weight <= 0:
        return

    for constituent in constituents:
        ticker = constituent['ticker']
        weight = constituent.get('weight', 0)
        target_weights[ticker] = target_weights.get(ticker, 0.0) + (
            target_weight * weight / total_internal_weight
        )


def _add_item_target(target_weights: dict, item: dict, target_weight: float) -> None:
    item_type = item.get('type')

    if item_type == 'strategy' and item.get('strategy') == 'weighted_split':
        _add_weighted_split_target(target_weights, item, target_weight)
        return

    ticker = _item_target_ticker(item)
    target_weights[ticker] = target_weights.get(ticker, 0.0) + target_weight


def get_cash_weight(fear_greed_index: float, cash_strategy: dict) -> float:
    """
    Determines cash weight based on Fear & Greed index.
    Note: In Extreme Fear, uses min cash + leverage for aggressive positioning.

    Args:
        fear_greed_index: Current F&G index value (0-100)
        cash_strategy: Dict with 'min', 'mid', 'max' cash weights

    Returns:
        Cash weight (0.0 to 1.0)
    """
    if fear_greed_index <= 20:
        # Extreme Fear -> Aggressive (min cash + leverage)
        return cash_strategy['min']
    elif fear_greed_index > 80:
        # Extreme Greed -> Defensive (max cash)
        return cash_strategy['max']
    else:
        # Neutral
        return cash_strategy['mid']


def calculate_target_weights(
    current_weights: dict,
    config: dict,
    fear_greed_index: float = 50.0
) -> tuple:
    """
    Calculates target weights based on new allocation logic.

    Args:
        current_weights: Current portfolio weights (ticker -> weight)
        config: Portfolio configuration
        fear_greed_index: Current F&G index (default: 50 = neutral)

    Returns:
        Tuple of (target_weights, total_score, cash_weight)
    """
    # 1. Reserve cash according to the Fear & Greed regime.
    cash_strategy = config.get('cash_strategy', {'min': 0.10, 'mid': 0.20, 'max': 0.30})
    cash_weight = get_cash_weight(fear_greed_index, cash_strategy)

    # 2. Add fixed leverage sleeves only during Extreme Fear.
    leverage_allocation = {}
    leverage_total = 0.0
    if fear_greed_index <= 20:
        leverage_allocation = {'SOXL': 0.05, 'TQQQ': 0.05}
        leverage_total = sum(leverage_allocation.values())

    # 3. Allocate the remaining portfolio weight to stocks.
    stock_total = 1.0 - cash_weight - leverage_total

    # 4. Calculate the explicit core score base.
    core_items = config.get('core', [])
    satellite_items = config.get('satellites', [])
    core_score = sum(item['score'] for item in core_items)
    satellite_scores = [
        item.get('ratio', 0.0) * core_score
        for item in satellite_items
    ]
    total_score = core_score + sum(satellite_scores)

    if total_score == 0:
        return {}, 0, cash_weight

    target_weights = {}

    # 5. Assign target weights for core and satellite items.
    for item in core_items:
        item_target = (item['score'] / total_score) * stock_total
        _add_item_target(target_weights, item, item_target)

    for item, score in zip(satellite_items, satellite_scores):
        item_target = (score / total_score) * stock_total
        _add_item_target(target_weights, item, item_target)

    # 6. Add the Extreme Fear leverage allocation.
    for ticker, weight in leverage_allocation.items():
        target_weights[ticker] = target_weights.get(ticker, 0.0) + weight

    return target_weights, total_score, cash_weight


def calculate_current_group_weights(
    current_weights: dict,
    config: dict
) -> dict:
    """
    Calculates current holdings with constituents merged into main ticker.

    For each group, the current weight of main_ticker is calculated as:
    main_ticker_current + sum(constituents_current)

    Args:
        current_weights: Current portfolio weights (ticker -> weight)
        config: Portfolio configuration

    Returns:
        Merged current weights (main_ticker includes constituents)
    """
    merged_weights = dict(current_weights)

    for group in _iter_allocation_items(config):
        if group.get('type') != 'group':
            continue

        main_ticker = group['main_ticker']
        constituents = group.get('constituents', [])

        # Sum constituents into main ticker
        constituent_total = 0.0
        for constituent in constituents:
            if constituent in merged_weights:
                constituent_total += merged_weights.pop(constituent)

        # Add to main ticker (create if not exists)
        merged_weights[main_ticker] = merged_weights.get(main_ticker, 0.0) + constituent_total

    return merged_weights


def calculate_rebalancing(
    current_weights: dict,
    config: dict,
    fear_greed_index: float = 50.0
) -> dict:
    """
    Calculates the difference between target and current weights for rebalancing.

    Args:
        current_weights: Current portfolio weights
        config: Portfolio configuration
        fear_greed_index: Current F&G index

    Returns:
        Dict with ticker -> {'target': float, 'current': float, 'diff': float}
    """
    target_weights, _, cash_weight = calculate_target_weights(
        current_weights, config, fear_greed_index
    )

    # Merge current weights (constituents into main ticker)
    merged_current = calculate_current_group_weights(current_weights, config)

    result = {}

    # All tickers from both target and current
    all_tickers = set(target_weights.keys()) | set(merged_current.keys())

    for ticker in all_tickers:
        target = target_weights.get(ticker, 0.0)
        current = merged_current.get(ticker, 0.0)
        diff = target - current

        result[ticker] = {
            'target': target,
            'current': current,
            'diff': diff
        }

    return result


if __name__ == "__main__":
    import unicodedata

    config = load_json(ConfigFile.PORTFOLIO_WEIGHTS)

    # Mock current weights for testing
    mock_current_weights = {
        "QQQ": 0.0204,
        "379810": 0.0383,
        "379800": 0.0751,
        "490490": 0.0028,
        "QQQM": 0.15,
        "VOO": 0.10,
    }

    # Test with different F&G values
    test_fg_values = [15, 50, 85]

    for fg in test_fg_values:
        print(f"\n{'='*60}")
        print(f"F&G Index: {fg}")
        print('='*60)

        targets, score, cash = calculate_target_weights(mock_current_weights, config, fg)

        print(f"Cash Weight: {cash*100:.1f}%")
        print(f"Stock Total: {(1-cash)*100:.1f}%")
        print(f"Total Score: {score:.2f}")

        # Load stock names for display
        import os
        import json
        script_dir = os.path.dirname(os.path.abspath(__file__))
        stock_config_file = os.path.join(script_dir, "stock_configuration.json")
        ticker_map = {}
        if os.path.exists(stock_config_file):
            with open(stock_config_file, 'r', encoding='utf-8') as f:
                stock_config = json.load(f)
            for region in stock_config:
                for stock in stock_config[region]:
                    ticker = stock.get('ticker')
                    name = stock.get('name')
                    if ticker and name:
                        ticker_map[ticker] = name

        # Sort by target weight
        sorted_tickers = sorted(targets.keys(), key=lambda t: targets[t], reverse=True)

        print(f"\n{'Ticker':<15} {'Target %':>10}")
        print("-" * 30)

        for ticker in sorted_tickers:
            weight = targets[ticker]
            if weight > 0.001:  # Skip near-zero weights
                print(f"{ticker:<15} {weight*100:>9.2f}%")

    # Test rebalancing calculation
    print(f"\n{'='*60}")
    print("Rebalancing Analysis (F&G=50)")
    print('='*60)

    rebalance = calculate_rebalancing(mock_current_weights, config, 50)
    sorted_rebalance = sorted(rebalance.items(), key=lambda x: abs(x[1]['diff']), reverse=True)

    print(f"\n{'Ticker':<15} {'Target':>10} {'Current':>10} {'Diff':>10}")
    print("-" * 50)

    for ticker, data in sorted_rebalance:
        if abs(data['diff']) > 0.001:  # Only show meaningful differences
            print(f"{ticker:<15} {data['target']*100:>9.2f}% {data['current']*100:>9.2f}% {data['diff']*100:>+9.2f}%")
