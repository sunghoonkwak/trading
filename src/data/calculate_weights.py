"""
Portfolio Weight Calculation

Allocation logic:
1. Cash allocation based on F&G index:
   - F&G <= 20 (Extreme Fear): max cash (0.3)
   - 20 < F&G <= 80 (Neutral): mid cash (0.2)
   - F&G > 80 (Extreme Greed): min cash (0.1)

2. Stock total = 1.0 - cash

3. Relative score-based allocation:
   - Each stock's score is calculated based on its ratio or target_score
   - Target weight = (score / total_score) * stock_total

4. Group handling:
   - Target: main_ticker gets full group target (constituents don't reduce it)
   - Current: main_ticker's holding + sum of constituents' holdings
"""

import json
import os

def load_config(config_path=None):
    """Loads the portfolio configuration from a JSON file."""
    if config_path is None:
        config_path = os.path.join(
            os.path.expanduser("~"), "KIS_config", "portfolio_weights.json"
        )
    elif not os.path.isabs(config_path):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, config_path)

    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_cash_weight(fear_greed_index: float, cash_strategy: dict) -> float:
    """
    Determines cash weight based on Fear & Greed index.

    Args:
        fear_greed_index: Current F&G index value (0-100)
        cash_strategy: Dict with 'min', 'mid', 'max' cash weights

    Returns:
        Cash weight (0.0 to 1.0)
    """
    if fear_greed_index <= 20:
        # Extreme Fear -> Hold more cash
        return cash_strategy['max']
    elif fear_greed_index > 80:
        # Extreme Greed -> Hold less cash
        return cash_strategy['min']
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
    # 1. Calculate cash weight based on F&G
    cash_strategy = config.get('cash_strategy', {'min': 0.1, 'mid': 0.2, 'max': 0.3})
    cash_weight = get_cash_weight(fear_greed_index, cash_strategy)

    # 2. Stock total = 1.0 - cash
    stock_total = 1.0 - cash_weight

    # 3. Calculate total score (for relative allocation)
    # Groups: sum of target_scores
    total_group_score = sum(group['target_score'] for group in config.get('groups', []))

    # Individual stocks: ratio * base (where base = total_group_score for consistency)
    individual_stocks = config.get('individual_stocks', [])
    total_individual_score = sum(
        item['ratio'] * total_group_score
        for item in individual_stocks
    )

    total_score = total_group_score + total_individual_score

    if total_score == 0:
        return {}, 0, cash_weight

    target_weights = {}

    # 4. Assign weights for individual stocks
    for item in individual_stocks:
        ticker = item['ticker']
        score = item['ratio'] * total_group_score
        target_weights[ticker] = (score / total_score) * stock_total

    # 5. Distribute KR Dividend Strategy (Sub-allocation)
    if "kr_dividend_strategy" in config:
        kr_strat = config["kr_dividend_strategy"]
        source_key = kr_strat.get("source_ticker")

        if source_key and source_key in target_weights:
            total_kr_weight = target_weights.pop(source_key)

            constituents = kr_strat.get("constituents", [])
            total_internal_weight = sum(c.get("weight", 0) for c in constituents)

            if total_internal_weight > 0:
                for c in constituents:
                    sub_ticker = c["ticker"]
                    internal_w = c["weight"]
                    target_weights[sub_ticker] = total_kr_weight * (internal_w / total_internal_weight)

    # 6. Assign weights for groups
    # Target: main_ticker gets full group target (no reduction for constituents)
    for group in config.get('groups', []):
        group_target_percent = (group['target_score'] / total_score) * stock_total
        main_ticker = group['main_ticker']

        # Main ticker gets the full group target
        target_weights[main_ticker] = group_target_percent

        # Constituents are NOT added to target_weights
        # They only contribute to current holding calculation

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

    for group in config.get('groups', []):
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

    # Load configuration
    config_file = "portfolio_weights.json"
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Try template directory first
    template_path = os.path.join(os.path.dirname(script_dir), "..", "templete", config_file)
    if os.path.exists(template_path):
        config_path = template_path
    else:
        config_path = os.path.join(script_dir, config_file)

    config = load_config(config_path)

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
