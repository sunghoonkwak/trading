import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import validate_config


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def _stock_config():
    return {
        "US": [
            {"ticker": "SOXL", "name": "Direxion Daily SOXL", "market": "AMS"},
            {"ticker": "TLTW", "name": "iShares TLTW", "market": "AMS"},
        ],
        "KR": [
            {"ticker": "005930", "name": "Samsung Electronics", "market": "KOSPI"},
        ],
    }


def _strategy_config():
    return {
        "cash_ticker": "TLTW",
        "raoeo": {
            "enabled": True,
            "targets": {
                "SOXL": {
                    "enabled": True,
                    "seed": 20000,
                    "duration": 40,
                    "phase": [
                        {
                            "name": "Phase 0",
                            "threshold": 0.1,
                            "buy": [
                                {
                                    "type": "normal",
                                    "ratio": 1,
                                    "price_percent_cap": 0.1,
                                },
                                {
                                    "type": "filling",
                                    "target_ratio": 0.1,
                                    "price_percent_cap": -0.05,
                                },
                            ],
                            "sell": [
                                {"type": "LOC", "ratio": 0.5, "profit": 0.2},
                                {"type": "Limit", "ratio": 0.5, "profit": 0.2},
                            ],
                        },
                        {
                            "name": "Phase 1",
                            "threshold": 0.2,
                            "buy": [{"type": "normal", "ratio": 1}],
                            "sell": [{"type": "LOC", "ratio": 1, "profit": 0.1}],
                        },
                        {
                            "name": "Fallback",
                            "buy": [{"type": "average", "ratio": 1}],
                            "sell": [{"type": "Limit", "ratio": 1, "profit": 0.1}],
                        },
                    ],
                }
            },
        },
    }


def test_valid_strategy_config_has_no_errors():
    errors = validate_config.validate_strategy_config(
        _strategy_config(),
        _stock_config(),
    )

    assert errors == []


def test_reports_unknown_enabled_raoeo_ticker():
    config = _strategy_config()
    config["raoeo"]["targets"]["MISSING"] = config["raoeo"]["targets"].pop("SOXL")

    errors = validate_config.validate_strategy_config(config, _stock_config())

    assert any("MISSING" in error and "stock_configuration" in error for error in errors)


def test_reports_non_positive_seed_and_duration():
    config = _strategy_config()
    target = config["raoeo"]["targets"]["SOXL"]
    target["seed"] = 0
    target["duration"] = -1

    errors = validate_config.validate_strategy_config(config, _stock_config())

    assert any("SOXL.seed" in error for error in errors)
    assert any("SOXL.duration" in error for error in errors)


def test_reports_thresholds_that_are_not_ascending():
    config = _strategy_config()
    phases = config["raoeo"]["targets"]["SOXL"]["phase"]
    phases[0]["threshold"] = 0.3
    phases[1]["threshold"] = 0.2

    errors = validate_config.validate_strategy_config(config, _stock_config())

    assert any("threshold" in error and "ascending" in error for error in errors)


def test_reports_invalid_buy_sell_ratio_and_profit():
    config = _strategy_config()
    phase = config["raoeo"]["targets"]["SOXL"]["phase"][0]
    phase["buy"][0]["ratio"] = 2.5
    phase["sell"][0]["ratio"] = -0.1
    phase["sell"][1]["profit"] = 0.8

    errors = validate_config.validate_strategy_config(config, _stock_config())

    assert any("buy[0].ratio" in error for error in errors)
    assert any("sell[0].ratio" in error for error in errors)
    assert any("sell[1].profit" in error for error in errors)


def test_cli_returns_failure_for_invalid_config(tmp_path, capsys):
    config = _strategy_config()
    config["raoeo"]["targets"]["SOXL"]["seed"] = 0
    config_path = tmp_path / "strategy_config.json"
    stock_path = tmp_path / "stock_configuration.json"
    _write_json(config_path, config)
    _write_json(stock_path, _stock_config())

    exit_code = validate_config.main(
        [
            "--config",
            str(config_path),
            "--stocks",
            str(stock_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "SOXL.seed" in output


def test_cli_success_output_lists_validated_checks(tmp_path, capsys):
    config_path = tmp_path / "strategy_config.json"
    stock_path = tmp_path / "stock_configuration.json"
    _write_json(config_path, _strategy_config())
    _write_json(stock_path, _stock_config())

    exit_code = validate_config.main(
        [
            "--config",
            str(config_path),
            "--stocks",
            str(stock_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Config validation passed" in output
    assert f"Strategy config: {config_path}" in output
    assert f"Stock config: {stock_path}" in output
    assert "RAOEO targets: SOXL" in output
    assert "cash_ticker registration" in output
    assert "seed and duration are positive" in output
    assert "phase thresholds are ascending" in output
    assert "buy/sell ratios and profits are in range" in output
    assert "ticker registration" in output


def test_default_config_path_points_to_user_kis_config():
    expected = Path.home() / "KIS_config" / "strategy_config.json"

    assert validate_config.DEFAULT_CONFIG_PATH == expected
