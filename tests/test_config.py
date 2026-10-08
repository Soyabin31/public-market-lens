from pathlib import Path

import pytest

from marketlens.config import (
    CONFIG_DIR,
    DATA_DIR,
    MODELS_DIR,
    PROJECT_ROOT,
    get_config_path,
    load_all_configs,
    load_and_validate_configs,
    load_yaml,
    validate_config,
)


def test_project_directories():
    assert PROJECT_ROOT.name in {"market-lens", "public-market-lens"}
    assert CONFIG_DIR.name == "config"
    assert DATA_DIR.name == "data"
    assert MODELS_DIR.name == "models"


def test_config_path():
    path = get_config_path("symbols.yaml")

    assert path.name == "symbols.yaml"
    assert path.parent == CONFIG_DIR


def test_symbols_config_loads():
    config = load_yaml("symbols.yaml")

    assert "markets" in config
    assert "stocks" in config

    assert "^NSEI" in config["markets"]["india"]["benchmark_symbols"]
    assert "^GSPC" in config["markets"]["us"]["benchmark_symbols"]

    assert config["stocks"]["india"]["universe"] == "nifty_50"
    assert config["stocks"]["us"]["universe"] == "sp500"


def test_all_configs_load():
    config = load_all_configs()

    assert set(config) == {
        "symbols",
        "sources",
        "mood",
        "model",
        "costs",
    }


def test_configuration_is_valid():
    config = load_and_validate_configs()

    assert config["mood"]["score"]["maximum"] == 100
    assert config["mood"]["score"]["minimum"] == 0


def test_mood_weights_sum_to_one():
    config = load_yaml("mood.yaml")

    weights = config["score"]["weights"]

    assert sum(weights.values()) == pytest.approx(1.0)


def test_backtest_requires_transaction_costs():
    config = load_yaml("costs.yaml")

    assert config["backtest"]["require_transaction_costs"] is True


def test_validate_config_rejects_invalid_mood_weights():
    config = load_all_configs()

    config["mood"]["score"]["weights"]["trend"] = 0.50

    with pytest.raises(ValueError, match="sum to 1.0"):
        validate_config(config)