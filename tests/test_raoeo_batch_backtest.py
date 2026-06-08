import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "backtest" / "raoeo"))

import batch_backtest


def test_month_starts_include_both_bounds():
    dates = batch_backtest.month_starts("2026-01", "2026-03")

    assert dates == [
        datetime(2026, 1, 1),
        datetime(2026, 2, 1),
        datetime(2026, 3, 1),
    ]


def test_parse_benchmark_list_normalizes_and_deduplicates():
    benchmarks = batch_backtest.parse_benchmark_list("soxx, VOO,SOXX, qqq")

    assert benchmarks == ["SOXX", "VOO", "QQQ"]


def test_apply_cash_ticker_option_can_disable_config_cash_ticker():
    config = {"cash_ticker": "TLTW", "seed": 1000}

    applied = batch_backtest.apply_cash_ticker_option(
        config,
        cash_ticker=None,
        no_cash_ticker=True,
    )

    assert applied == {"seed": 1000}
    assert config["cash_ticker"] == "TLTW"


def test_build_output_paths_can_add_suffix_for_sample_runs():
    report_path, plot_path = batch_backtest.build_output_paths(
        script_dir=ROOT / "scripts" / "backtest" / "raoeo",
        ticker="SOXL",
        cash_ticker=None,
        output_suffix="sample",
    )

    assert report_path.name == "batch_analysis_report_sample.md"
    assert plot_path.name == "batch_cagr_distribution_sample.png"
