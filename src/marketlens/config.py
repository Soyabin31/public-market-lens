from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"


CONFIG_FILES = {
    "symbols": "symbols.yaml",
    "sources": "sources.yaml",
    "mood": "mood.yaml",
    "model": "model.yaml",
    "costs": "costs.yaml",
}


def get_config_path(filename: str) -> Path:
    """
    Return the absolute path of a configuration file.
    """
    return CONFIG_DIR / filename


def load_yaml(filename: str) -> dict[str, Any]:
    """
    Load a YAML configuration file.

    Args:
        filename: File name located under the config directory.

    Returns:
        Parsed YAML content as a dictionary.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        ValueError: If the YAML root is not a mapping.
    """
    path = get_config_path(filename)

    if not path.exists():
        raise FileNotFoundError(
            f"Configuration file does not exist: {path}"
        )

    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if data is None:
        return {}

    if not isinstance(data, dict):
        raise ValueError(
            f"Configuration root must be a mapping: {path}"
        )

    return data


def load_all_configs() -> dict[str, dict[str, Any]]:
    """
    Load all Market Lens YAML configuration files.

    Returns:
        Dictionary keyed by configuration name.
    """
    return {
        name: load_yaml(filename)
        for name, filename in CONFIG_FILES.items()
    }


def validate_config(config: dict[str, dict[str, Any]]) -> None:
    """
    Validate the minimum structural requirements of the configuration.

    This is intentionally lightweight at this stage.
    Domain-specific validation will be added alongside each feature.
    """

    required_sections = {
        "symbols",
        "sources",
        "mood",
        "model",
        "costs",
    }

    missing = required_sections - config.keys()

    if missing:
        raise ValueError(
            f"Missing configuration sections: {sorted(missing)}"
        )

    symbols = config["symbols"]

    if "markets" not in symbols:
        raise ValueError("symbols.yaml must define 'markets'")

    if "stocks" not in symbols:
        raise ValueError("symbols.yaml must define 'stocks'")

    mood = config["mood"]

    if "score" not in mood:
        raise ValueError("mood.yaml must define 'score'")

    weights = mood["score"].get("weights", {})

    expected_weights = {
        "trend",
        "momentum",
        "volatility",
        "breadth",
        "news",
    }

    if set(weights) != expected_weights:
        raise ValueError(
            "mood.yaml weights must contain exactly: "
            f"{sorted(expected_weights)}"
        )

    weight_sum = sum(float(value) for value in weights.values())

    if abs(weight_sum - 1.0) > 1e-9:
        raise ValueError(
            f"Mood weights must sum to 1.0, got {weight_sum}"
        )

    if "labels" not in mood:
        raise ValueError("mood.yaml must define 'labels'")

    costs = config["costs"]

    if "backtest" not in costs:
        raise ValueError(
            "costs.yaml must define 'backtest'"
        )

    if not costs["backtest"].get("require_transaction_costs", False):
        raise ValueError(
            "Backtest must require transaction costs"
        )


def load_and_validate_configs() -> dict[str, dict[str, Any]]:
    """
    Load all configuration files and validate their structure.
    """
    config = load_all_configs()
    validate_config(config)
    return config