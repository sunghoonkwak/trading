import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from data.calculate_weights import (
    calculate_current_group_weights,
    calculate_target_weights,
)


def test_satellite_group_uses_core_score_without_expanding_base():
    config = {
        "cash_strategy": {"min": 0.1, "mid": 0.2, "max": 0.3},
        "core": [
            {
                "type": "group",
                "name": "Nasdaq100",
                "score": 120,
                "main_ticker": "QQQM",
                "constituents": ["QQQ"],
            },
            {
                "type": "group",
                "name": "S&P500",
                "score": 40,
                "main_ticker": "VOO",
                "constituents": [],
            },
            {
                "type": "group",
                "name": "Dividend",
                "score": 20,
                "main_ticker": "SCHD",
                "constituents": [],
            },
        ],
        "satellites": [
            {
                "type": "group",
                "name": "Bonds",
                "ratio": 0.1,
                "main_ticker": "TLTW",
                "constituents": ["TLT"],
            }
        ],
    }

    targets, total_score, cash_weight = calculate_target_weights({}, config, 50)

    assert cash_weight == pytest.approx(0.2)
    assert total_score == pytest.approx(180)
    assert targets["QQQM"] == pytest.approx((120 / 180) * 0.8)
    assert "TLTW" not in targets


def test_satellite_individuals_and_weighted_split_use_core_score():
    config = {
        "cash_strategy": {"min": 0.1, "mid": 0.2, "max": 0.3},
        "core": [
            {
                "type": "group",
                "name": "Nasdaq100",
                "score": 120,
                "main_ticker": "QQQM",
                "constituents": [],
            },
            {
                "type": "group",
                "name": "S&P500",
                "score": 40,
                "main_ticker": "VOO",
                "constituents": [],
            },
            {
                "type": "group",
                "name": "Dividend",
                "score": 20,
                "main_ticker": "SCHD",
                "constituents": [],
            },
        ],
        "satellites": [
            {"type": "individual", "ticker": "TSM", "ratio": 0.1},
            {
                "type": "strategy",
                "name": "KR_DIV",
                "strategy": "weighted_split",
                "ratio": 0.2,
                "constituents": [
                    {"ticker": "005385", "weight": 1},
                    {"ticker": "086790", "weight": 3},
                ],
            },
        ],
    }

    targets, total_score, _ = calculate_target_weights({}, config, 50)

    assert total_score == pytest.approx(234)
    assert targets["TSM"] == pytest.approx((18 / 234) * 0.8)
    kr_div_target = (36 / 234) * 0.8
    assert targets["005385"] == pytest.approx(kr_div_target * 0.25)
    assert targets["086790"] == pytest.approx(kr_div_target * 0.75)
    assert "KR_DIV" not in targets


def test_current_group_weights_merge_core_and_satellite_constituents():
    config = {
        "core": [
            {
                "type": "group",
                "name": "Nasdaq100",
                "score": 120,
                "main_ticker": "QQQM",
                "constituents": ["QQQ"],
            }
        ],
        "satellites": [
            {
                "type": "group",
                "name": "Bonds",
                "ratio": 0.1,
                "main_ticker": "TLTW",
                "constituents": ["TLT"],
            }
        ],
    }

    merged = calculate_current_group_weights(
        {"QQQM": 0.1, "QQQ": 0.2, "TLTW": 0.03, "TLT": 0.04},
        config,
    )

    assert merged["QQQM"] == pytest.approx(0.3)
    assert merged["TLTW"] == pytest.approx(0.07)
    assert "QQQ" not in merged
    assert "TLT" not in merged


def test_extreme_fear_leverage_allocation_still_applies():
    config = {
        "cash_strategy": {"min": 0.1, "mid": 0.2, "max": 0.3},
        "core": [
            {
                "type": "individual",
                "ticker": "SCHD",
                "score": 100,
            }
        ],
        "satellites": [],
    }

    targets, _, cash_weight = calculate_target_weights({}, config, 10)

    assert cash_weight == pytest.approx(0.1)
    assert targets["SCHD"] == pytest.approx(0.8)
    assert targets["SOXL"] == pytest.approx(0.05)
    assert targets["TQQQ"] == pytest.approx(0.05)


def test_weight_diffs_merge_non_bonds_group_constituents(monkeypatch):
    from data import data_service

    monkeypatch.setattr(
        data_service,
        "load_json",
        lambda _config_file: {
            "cash_strategy": {"min": 0.1, "mid": 0.2, "max": 0.3},
            "core": [],
            "satellites": [
                {
                    "type": "group",
                    "name": "Treasury",
                    "ratio": 0.1,
                    "main_ticker": "TLTW",
                    "constituents": ["TLT"],
                }
            ],
        },
    )
    monkeypatch.setattr(data_service, "get_fear_and_greed", lambda: 50)
    monkeypatch.setattr(
        data_service,
        "get_portfolio_data",
        lambda scope="all": {
            "merged_data": {
                "TLTW": {
                    "name": "TLTW",
                    "type": "STOCK",
                    "cur_price": 30,
                    "currency": "USD",
                    "current_value_usd": 300,
                },
                "TLT": {
                    "name": "TLT",
                    "type": "STOCK",
                    "cur_price": 90,
                    "currency": "USD",
                    "current_value_usd": 400,
                },
            },
            "total_value_usd": 10000,
            "targets": {"TLTW": 0.05},
            "current_weights": {"TLTW": 0.03, "TLT": 0.04},
            "exchange_rate": 1.0,
        },
    )

    diffs, _, _ = data_service.get_weight_diffs("all")

    assert {d["ticker"] for d in diffs} == {"TLTW"}
    assert diffs[0]["cur_w"] == pytest.approx(0.07)
    assert diffs[0]["tgt_w"] == pytest.approx(0.05)


def test_weight_diffs_exclude_bonds_group_and_count_it_as_cash(monkeypatch):
    from data import data_service

    monkeypatch.setattr(
        data_service,
        "load_json",
        lambda _config_file: {
            "cash_strategy": {"min": 0.1, "mid": 0.2, "max": 0.3},
            "core": [],
            "satellites": [
                {
                    "type": "group",
                    "name": "Bonds",
                    "ratio": 0.1,
                    "main_ticker": "TLTW",
                    "constituents": ["TLT"],
                },
                {"type": "individual", "ticker": "TSM", "ratio": 0.1},
            ],
        },
    )
    monkeypatch.setattr(data_service, "get_fear_and_greed", lambda: 50)
    monkeypatch.setattr(
        data_service,
        "get_portfolio_data",
        lambda scope="all": {
            "merged_data": {
                "USD cash": {
                    "name": "USD cash",
                    "type": "CASH",
                    "current_value_usd": 1000,
                },
                "TLTW": {
                    "name": "TLTW",
                    "type": "STOCK",
                    "cur_price": 30,
                    "currency": "USD",
                    "current_value_usd": 300,
                },
                "TLT": {
                    "name": "TLT",
                    "type": "STOCK",
                    "cur_price": 90,
                    "currency": "USD",
                    "current_value_usd": 400,
                },
                "TSM": {
                    "name": "TSM",
                    "type": "STOCK",
                    "cur_price": 200,
                    "currency": "USD",
                    "current_value_usd": 500,
                },
            },
            "total_value_usd": 10000,
            "targets": {"TLTW": 0.05, "TSM": 0.10},
            "current_weights": {"USD cash": 0.10, "TLTW": 0.03, "TLT": 0.04, "TSM": 0.05},
            "exchange_rate": 1.0,
        },
    )

    diffs, _, cash_info = data_service.get_weight_diffs("all")

    assert {d["ticker"] for d in diffs} == {"TSM"}
    assert cash_info["current"] == pytest.approx(0.17)
    assert cash_info["target"] == pytest.approx(0.20)


def test_weight_diffs_include_group_value_and_main_ticker_trade_qty(monkeypatch):
    from data import data_service

    monkeypatch.setattr(
        data_service,
        "load_json",
        lambda _config_file: {
            "cash_strategy": {"min": 0.1, "mid": 0.2, "max": 0.3},
            "core": [
                {
                    "type": "group",
                    "name": "Nasdaq100",
                    "score": 100,
                    "main_ticker": "QQQM",
                    "constituents": ["QQQ"],
                }
            ],
            "satellites": [],
        },
    )
    monkeypatch.setattr(data_service, "get_fear_and_greed", lambda: 50)
    monkeypatch.setattr(
        data_service,
        "get_portfolio_data",
        lambda scope="all": {
            "merged_data": {
                "QQQM": {
                    "name": "QQQM",
                    "type": "STOCK",
                    "cur_price": 200,
                    "currency": "USD",
                    "current_value_usd": 1000,
                },
                "QQQ": {
                    "name": "QQQ",
                    "type": "STOCK",
                    "cur_price": 500,
                    "currency": "USD",
                    "current_value_usd": 3000,
                },
            },
            "total_value_usd": 10000,
            "targets": {"QQQM": 0.60},
            "current_weights": {"QQQM": 0.10, "QQQ": 0.30},
            "exchange_rate": 1.0,
        },
    )

    diffs, _, _ = data_service.get_weight_diffs("all")

    assert len(diffs) == 1
    assert diffs[0]["ticker"] == "QQQM"
    assert diffs[0]["name"] == "Nasdaq100"
    assert diffs[0]["is_group"] is True
    assert diffs[0]["current_value_usd"] == pytest.approx(4000)
    assert diffs[0]["target_value_usd"] == pytest.approx(6000)
    assert diffs[0]["qty_diff"] == 10
