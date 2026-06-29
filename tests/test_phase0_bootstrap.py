"""Phase 0 bootstrap validation."""
import pytest
from pathlib import Path

ROOT = Path(__file__).parents[1]

REQUIRED_DIRS = [
    "config",
    "knowledge",
    "src/collector",
    "src/engine",
    "src/features",
    "src/detectors",
    "src/simulator",
    "src/statistics",
    "src/utils",
    "outputs/candles",
    "outputs/features",
    "outputs/trades",
    "outputs/reports",
    "tests/unit",
    "tests/integration",
    "tests/fixtures",
    "memory",
]

REQUIRED_FILES = [
    "CLAUDE.md",
    "PROJECT_CONTEXT.md",
    "IMPLEMENTATION_PLAN.md",
    "config/models.yaml",
    "src/utils/config_loader.py",
    ".gitignore",
]


@pytest.mark.parametrize("d", REQUIRED_DIRS)
def test_directory_exists(d):
    assert (ROOT / d).is_dir(), f"Missing directory: {d}"


@pytest.mark.parametrize("f", REQUIRED_FILES)
def test_file_exists(f):
    assert (ROOT / f).is_file(), f"Missing file: {f}"


def test_models_yaml_loads():
    from src.utils.config_loader import load_models_config
    config = load_models_config()
    assert config["version"] == 1


def test_models_yaml_policies():
    from src.utils.config_loader import load_models_config
    config = load_models_config()
    policies = config["policies"]
    assert policies["never_use_future_candles"] is True
    assert policies["never_use_llm_for_math"] is True
    assert policies["deterministic_first"] is True


def test_routing_has_deterministic_engine():
    from src.utils.config_loader import load_models_config
    config = load_models_config()
    routing = config["routing"]
    deterministic_routes = [k for k, v in routing.items() if v == "deterministic_engine"]
    assert len(deterministic_routes) >= 4, "Expected at least 4 routes to deterministic_engine"
