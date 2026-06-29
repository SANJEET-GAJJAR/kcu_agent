"""Load and validate config/models.yaml for the model router."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

_DEFAULT_CONFIG_PATH = Path(__file__).parents[2] / "config" / "models.yaml"


@dataclass
class ModelEntry:
    provider: str
    model: str
    command: str
    signin_command: str | None = None


@dataclass
class RouterConfig:
    implementation_model: ModelEntry
    architecture_model_provider: str
    fallback_order: list[ModelEntry] = field(default_factory=list)
    timeout_seconds: int = 300
    max_retries: int = 2


class RouterConfigError(Exception):
    """Raised when config/models.yaml is missing required fields."""


def load_router_config(path: Path | None = None) -> RouterConfig:
    """Parse config/models.yaml and return a RouterConfig.

    Raises RouterConfigError if required fields are absent.
    Never falls back to the architecture model (Claude) for implementation tasks.
    """
    config_path = path or _DEFAULT_CONFIG_PATH
    if not config_path.exists():
        raise RouterConfigError(f"models.yaml not found at {config_path}")

    raw = yaml.safe_load(config_path.read_text())

    impl_raw = raw.get("implementation_model")
    if not impl_raw:
        raise RouterConfigError("models.yaml missing 'implementation_model' section")
    for key in ("provider", "model", "command"):
        if not impl_raw.get(key):
            raise RouterConfigError(
                f"implementation_model missing required field '{key}' in models.yaml"
            )

    arch_raw = raw.get("architecture_model", {})
    arch_provider = arch_raw.get("provider", "")

    impl = ModelEntry(
        provider=impl_raw["provider"],
        model=impl_raw["model"],
        command=impl_raw["command"],
        signin_command=impl_raw.get("signin_command"),
    )

    fallbacks: list[ModelEntry] = []
    for fb in impl_raw.get("fallback_order", []):
        if not fb.get("provider") or not fb.get("model") or not fb.get("command"):
            continue
        fallbacks.append(ModelEntry(
            provider=fb["provider"],
            model=fb["model"],
            command=fb["command"],
        ))

    defaults = raw.get("defaults", {})
    return RouterConfig(
        implementation_model=impl,
        architecture_model_provider=arch_provider,
        fallback_order=fallbacks,
        timeout_seconds=int(defaults.get("timeout_seconds", 300)),
        max_retries=int(defaults.get("max_retries", 2)),
    )
