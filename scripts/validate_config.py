#!/usr/bin/env python3
"""Validate trading strategy configuration before starting Docker runtime."""
import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = Path.home() / "KIS_config" / "strategy_config.json"
FALLBACK_CONFIG_PATH = REPO_ROOT / "templates" / "strategy_config.json"
DEFAULT_STOCKS_PATH = REPO_ROOT / "src" / "stock_configuration.json"

ALLOWED_BUY_TYPES = {"normal", "average", "filling"}
ALLOWED_SELL_TYPES = {"LOC", "Limit"}


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _is_disabled(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "on"}
    return False


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _registered_tickers(stock_config: Dict[str, Any]) -> Set[str]:
    tickers: Set[str] = set()
    for entries in stock_config.values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict) and entry.get("ticker"):
                tickers.add(str(entry["ticker"]))
    return tickers


def _require_positive_number(
    errors: List[str],
    value: Any,
    label: str,
) -> None:
    number = _number(value)
    if number is None or number <= 0:
        errors.append(f"{label} must be a positive number")


def _validate_ratio(errors: List[str], value: Any, label: str) -> None:
    number = _number(value)
    if number is None or not 0 <= number <= 2:
        errors.append(f"{label} must be a number between 0 and 2")


def _validate_profit(errors: List[str], value: Any, label: str) -> None:
    number = _number(value)
    if number is None or not 0 <= number <= 0.5:
        errors.append(f"{label} must be a number between 0 and 0.5")


def _validate_optional_range(
    errors: List[str],
    item: Dict[str, Any],
    key: str,
    label: str,
    minimum: float,
    maximum: float,
) -> None:
    if key not in item:
        return
    number = _number(item[key])
    if number is None or not minimum <= number <= maximum:
        errors.append(f"{label}.{key} must be a number between {minimum:g} and {maximum:g}")


def _validate_phase_thresholds(
    errors: List[str],
    ticker: str,
    phases: Sequence[Any],
) -> None:
    previous: Optional[float] = None
    for index, phase in enumerate(phases):
        if not isinstance(phase, dict):
            errors.append(f"{ticker}.phase[{index}] must be an object")
            continue
        if "threshold" not in phase:
            continue
        threshold = _number(phase["threshold"])
        if threshold is None or not 0 < threshold <= 1:
            errors.append(f"{ticker}.phase[{index}].threshold must be a number between 0 and 1")
            continue
        if previous is not None and threshold <= previous:
            errors.append(f"{ticker}.phase thresholds must be ascending")
        previous = threshold


def _validate_buy_rules(
    errors: List[str],
    ticker: str,
    phase_index: int,
    rules: Any,
) -> None:
    if not isinstance(rules, list) or not rules:
        errors.append(f"{ticker}.phase[{phase_index}].buy must be a non-empty list")
        return
    for rule_index, rule in enumerate(rules):
        label = f"{ticker}.phase[{phase_index}].buy[{rule_index}]"
        if not isinstance(rule, dict):
            errors.append(f"{label} must be an object")
            continue
        if _is_disabled(rule.get("disable", False)):
            continue
        buy_type = rule.get("type")
        if buy_type not in ALLOWED_BUY_TYPES:
            errors.append(f"{label}.type must be one of {sorted(ALLOWED_BUY_TYPES)}")
        if "ratio" in rule:
            _validate_ratio(errors, rule["ratio"], f"{label}.ratio")
        elif buy_type != "filling":
            errors.append(f"{label}.ratio is required")
        _validate_optional_range(errors, rule, "price_percent_cap", label, -1, 1)
        if buy_type == "filling":
            _validate_optional_range(errors, rule, "target_ratio", label, 0, 2)
            if "target_ratio" not in rule:
                errors.append(f"{label}.target_ratio is required for filling buys")


def _validate_sell_rules(
    errors: List[str],
    ticker: str,
    phase_index: int,
    rules: Any,
) -> None:
    if not isinstance(rules, list):
        errors.append(f"{ticker}.phase[{phase_index}].sell must be a list")
        return
    for rule_index, rule in enumerate(rules):
        label = f"{ticker}.phase[{phase_index}].sell[{rule_index}]"
        if not isinstance(rule, dict):
            errors.append(f"{label} must be an object")
            continue
        if _is_disabled(rule.get("disable", False)):
            continue
        sell_type = rule.get("type")
        if sell_type not in ALLOWED_SELL_TYPES:
            errors.append(f"{label}.type must be one of {sorted(ALLOWED_SELL_TYPES)}")
        if "ratio" not in rule:
            errors.append(f"{label}.ratio is required")
        else:
            _validate_ratio(errors, rule["ratio"], f"{label}.ratio")
        if "profit" not in rule:
            errors.append(f"{label}.profit is required")
        else:
            _validate_profit(errors, rule["profit"], f"{label}.profit")


def _validate_raoeo_target(
    errors: List[str],
    ticker: str,
    target: Dict[str, Any],
    registered: Set[str],
) -> None:
    if ticker not in registered:
        errors.append(f"{ticker} is not registered in stock_configuration.json")

    _require_positive_number(errors, target.get("seed"), f"{ticker}.seed")
    _require_positive_number(errors, target.get("duration"), f"{ticker}.duration")

    phases = target.get("phase")
    if not isinstance(phases, list) or not phases:
        errors.append(f"{ticker}.phase must be a non-empty list")
        return

    _validate_phase_thresholds(errors, ticker, phases)
    for phase_index, phase in enumerate(phases):
        if not isinstance(phase, dict):
            continue
        _validate_buy_rules(errors, ticker, phase_index, phase.get("buy"))
        _validate_sell_rules(errors, ticker, phase_index, phase.get("sell", []))


def validate_strategy_config(
    strategy_config: Dict[str, Any],
    stock_config: Dict[str, Any],
) -> List[str]:
    """Return validation errors for strategy_config.json."""
    errors: List[str] = []
    registered = _registered_tickers(stock_config)

    cash_ticker = strategy_config.get("cash_ticker")
    if cash_ticker and str(cash_ticker) not in registered:
        errors.append(f"cash_ticker {cash_ticker} is not registered in stock_configuration.json")

    raoeo = strategy_config.get("raoeo", {})
    if not isinstance(raoeo, dict):
        return ["raoeo must be an object"]
    if not raoeo.get("enabled", False):
        return errors

    targets = raoeo.get("targets", {})
    if not isinstance(targets, dict) or not targets:
        errors.append("raoeo.targets must be a non-empty object when raoeo is enabled")
        return errors

    for ticker, target in targets.items():
        if not isinstance(target, dict):
            errors.append(f"{ticker} target must be an object")
            continue
        if not target.get("enabled", True):
            continue
        _validate_raoeo_target(errors, str(ticker), target, registered)

    return errors


def _enabled_raoeo_targets(strategy_config: Dict[str, Any]) -> List[str]:
    raoeo = strategy_config.get("raoeo", {})
    if not isinstance(raoeo, dict) or not raoeo.get("enabled", False):
        return []

    targets = raoeo.get("targets", {})
    if not isinstance(targets, dict):
        return []

    return [
        str(ticker)
        for ticker, target in targets.items()
        if isinstance(target, dict) and target.get("enabled", True)
    ]


def _success_report(
    config_path: Path,
    stocks_path: Path,
    strategy_config: Dict[str, Any],
) -> str:
    targets = _enabled_raoeo_targets(strategy_config)
    target_text = ", ".join(targets) if targets else "none"
    checks = [
        "cash_ticker registration",
        "RAOEO ticker registration",
        "seed and duration are positive",
        "phase thresholds are ascending",
        "buy/sell ratios and profits are in range",
        "buy/sell order types are supported",
        "filling buy target_ratio is present and in range",
    ]

    lines = [
        "Config validation passed",
        f"- Strategy config: {config_path}",
        f"- Stock config: {stocks_path}",
        f"- RAOEO targets: {target_text}",
        "- Checks:",
    ]
    lines.extend(f"  - {check}" for check in checks)
    return "\n".join(lines)


def _default_config_path() -> Path:
    if DEFAULT_CONFIG_PATH.exists():
        return DEFAULT_CONFIG_PATH
    return FALLBACK_CONFIG_PATH


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate strategy_config.json before starting the trading bot.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=_default_config_path(),
        help="Path to strategy_config.json",
    )
    parser.add_argument(
        "--stocks",
        type=Path,
        default=DEFAULT_STOCKS_PATH,
        help="Path to stock_configuration.json",
    )
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        strategy_config = _load_json(args.config)
        stock_config = _load_json(args.stocks)
    except FileNotFoundError as exc:
        print(f"Config validation failed: file not found: {exc.filename}")
        return 1
    except json.JSONDecodeError as exc:
        print(f"Config validation failed: invalid JSON in {exc.doc}: {exc}")
        return 1

    errors = validate_strategy_config(strategy_config, stock_config)
    if errors:
        print("Config validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(_success_report(args.config, args.stocks, strategy_config))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
