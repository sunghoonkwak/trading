import json
import os
import unicodedata

def load_config(config_path=None):
    """Loads the portfolio configuration from a JSON file."""
    if config_path is None:
        # Default path: ~/KIS_config/portfolio_weights.json
        config_path = os.path.join(os.path.expanduser("~"), "KIS_config", "portfolio_weights.json")
    elif not os.path.isabs(config_path):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, config_path)

    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def calculate_target_weights(current_weights, config, current_vix=None):
    """
    Calculates the target weights for the portfolio based on logical scores and US Index reference.

    The logic is:
    1. Base Score System:
       - Defined Groups (Nasdaq, S&P, Dividend) have fixed target scores (e.g. 100, 50, 15).
       - Individual Stocks have scores calculated as: Ratio * US_Index_Weight (165).
       - Fixed items (VIXY) have manual scores.

    2. Total Score Calculation:
       - Total Theoretical Score = Sum(Group Targets) + Sum(Individual Scores) + Sum(Fixed Scores).

    3. Target Percentage Calculation:
       - Individual/Fixed Tickers: Target% = Score / Total Score.
       - Groups: Group Target% = Group Score / Total Score.
         - The Group Target% is distributed:
           - "Constituents" (e.g. QQQ, KODEX) KEEP their current portfolio weight (User Rule).
           - "Main Ticker" (e.g. QQQM) takes the remaining weight:
             Main% = Group% - Sum(Current% of Constituents).

    Args:
        current_weights (dict): Existing portfolio weights.
        config (dict): Portfolio configuration.
        current_vix (float, optional): Current VIX index value. Defaults to 14.83 (from user example) if not provided.
    """
    if current_vix is None:
        current_vix = 14.83

    # 1. Calculate US Index Weight Base
    us_index_weight = sum(group['target_score'] for group in config['groups'])

    # 2. Calculate VIX Strategy Score
    vix_score = 0.0
    vix_ticker = None

    if 'vix_strategy' in config:
        v_cfg = config['vix_strategy']
        vix_ticker = v_cfg['ticker']
        # Formula: min(if(VIX < max, limit * (max - VIX) / scale, 0), limit)
        if current_vix < v_cfg['max']:
            raw_score = v_cfg['limit'] * (v_cfg['max'] - current_vix) / v_cfg['scale']
            vix_score = min(raw_score, v_cfg['limit'])
        else:
            vix_score = 0.0

    # 3. Calculate Total Score
    total_group_score = us_index_weight

    total_individual_score = sum(
        item['ratio'] * us_index_weight
        for item in config['individual_stocks']
    )

    total_fixed_score = sum(item['score'] for item in config.get('fixed_scores', []))

    total_score = total_group_score + total_individual_score + total_fixed_score + vix_score

    if total_score == 0:
        return {}, 0

    target_weights = {}

    # 4. Assign Weights for VIX
    if vix_ticker:
        target_weights[vix_ticker] = vix_score / total_score

    # 5. Assign Weights for Individual Stocks
    for item in config['individual_stocks']:
        ticker = item['ticker']
        score = item['ratio'] * us_index_weight
        target_weights[ticker] = score / total_score

    # 6. Distribute KR Dividend Strategy (Sub-allocation)
    if "kr_dividend_strategy" in config:
        kr_strat = config["kr_dividend_strategy"]
        source_key = kr_strat.get("source_ticker")

        if source_key and source_key in target_weights:
            total_kr_weight = target_weights.pop(source_key) # Remove the placeholder aggregation

            constituents = kr_strat.get("constituents", [])
            total_internal_weight = sum(c.get("weight", 0) for c in constituents)

            if total_internal_weight > 0:
                for c in constituents:
                    sub_ticker = c["ticker"]
                    internal_w = c["weight"]
                    # Allocate proportional weight
                    target_weights[sub_ticker] = total_kr_weight * (internal_w / total_internal_weight)

    # 3. Assign Weights for Fixed Score Items
    for item in config.get('fixed_scores', []):
        ticker = item['ticker']
        score = item['score']
        target_weights[ticker] = score / total_score

    # 4. Assign Weights for Groups
    for group in config['groups']:
        group_target_percent = group['target_score'] / total_score

        # Calculate weight consumed by legacy/fixed constituents
        used_weight = 0.0
        for constituent in group.get('constituents', []):
            # Target for constituent is its CURRENT weight (Fixed position logic)
            c_weight = current_weights.get(constituent, 0.0)
            target_weights[constituent] = c_weight
            used_weight += c_weight

        # Assign remaining weight to Main Ticker
        remaining_weight = group_target_percent - used_weight

        # Ensure non-negative (if current holdings exceed target, Main gets 0)
        target_weights[group['main_ticker']] = max(0.0, remaining_weight)

    return target_weights, total_score

if __name__ == "__main__":
    # Example Usage / Test
    try:
        config_file = "portfolio_weights.json"
        if not os.path.exists(config_file):
            # Fallback for running from different dir
            config_file = os.path.join(os.path.dirname(__file__), "portfolio_weights.json")

        config = load_config(config_file)

        # Mock Current Weights (approximate from user image for verification)
        # Note: These should be actual portfolio weight ratios (0.01 = 1%)
        mock_current_weights = {
            "QQQ": 0.0204,
            "379810": 0.0383,
            "379800": 0.0751,
            "490490": 0.0028
        }

        targets, score = calculate_target_weights(mock_current_weights, config)

        # Load stock configuration for names
        stock_config_file = "stock_configuration.json"
        if not os.path.exists(stock_config_file):
            stock_config_file = os.path.join(os.path.dirname(__file__), "stock_configuration.json")

        ticker_map = {}
        if os.path.exists(stock_config_file):
            stock_config = load_config(stock_config_file)
            for region in stock_config:
                for stock in stock_config[region]:
                    ticker = stock.get('ticker')
                    name = stock.get('name')
                    if ticker and name:
                        ticker_map[ticker] = name

        # Sort Logic: By Target % (Descending) -> then Ticker
        # This makes it easier to read high-weight items first
        all_tickers = sorted(targets.keys(), key=lambda t: targets[t], reverse=True)

        print(f"Total Calculated Score: {score:.3f}")

        # Column Headers
        h_name = "Name"
        h_ticker = "Ticker"
        h_target = "Target %"

        # Define Column Widths
        w_name = 40
        w_ticker = 15
        w_target = 10

        sep_len = w_name + 3 + w_ticker + 3 + w_target
        print("=" * sep_len)

        def get_display_width(s):
            w = 0
            for char in s:
                if unicodedata.east_asian_width(char) in ('W', 'F'):
                    w += 2
                else:
                    w += 1
            return w

        def pad_string(s, width):
            d_width = get_display_width(s)
            padding = width - d_width
            if padding < 0:
                # Truncate logic could be added here if strictly needed,
                # but for now let's just return as is or handle simple overflow
                return s + " " # minimal space
            return s + " " * padding

        header = f"{pad_string(h_name, w_name)} | {pad_string(h_ticker, w_ticker)} | {h_target}"
        print(header)
        print("-" * sep_len)

        for ticker in all_tickers:
            weight = targets[ticker]
            # Custom name handling for specific tickers if not in config
            if ticker == "국내 배당주":
                name = "국내 배당주"
            else:
                name = ticker_map.get(ticker, ticker) # Fallback to ticker if name not found

            val_str = f"{weight*100:6.2f}%"

            line = f"{pad_string(name, w_name)} | {pad_string(ticker, w_ticker)} | {val_str}"
            print(line)

    except Exception as e:
        print(f"An error occurred: {e}")
