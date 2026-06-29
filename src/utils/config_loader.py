"""Loads and validates config/models.yaml."""
from pathlib import Path
import yaml

_CONFIG_PATH = Path(__file__).parents[2] / "config" / "models.yaml"

_REQUIRED_SECTIONS = [
    "version",
    "defaults",
    "market_provider",
    "deterministic_engine",
    "implementation_model",
    "architecture_model",
    "review_model",
    "routing",
    "policies",
]


def load_models_config(path: Path = _CONFIG_PATH) -> dict:
    with open(path, "r") as f:
        config = yaml.safe_load(f)
    _validate(config)
    return config


def _validate(config: dict) -> None:
    missing = [s for s in _REQUIRED_SECTIONS if s not in config]
    if missing:
        raise ValueError(f"models.yaml missing required sections: {missing}")

    policies = config.get("policies", {})
    if not policies.get("never_use_future_candles"):
        raise ValueError("Policy 'never_use_future_candles' must be true")
    if not policies.get("never_use_llm_for_math"):
        raise ValueError("Policy 'never_use_llm_for_math' must be true")
