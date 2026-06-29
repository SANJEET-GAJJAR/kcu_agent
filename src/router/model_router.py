"""ModelRouter — public API for dispatching implementation tasks.

Usage:
    router = ModelRouter()
    output = router.run("implement_outcome_simulation", prompt="Write src/simulator/outcome.py ...")
    print(output)

The router reads config/models.yaml, selects implementation_model, and dispatches
the prompt via subprocess. All attempts are logged to outputs/model_router/router_log.jsonl.
"""
from __future__ import annotations

from pathlib import Path

from src.router.config_loader import RouterConfig, load_router_config
from src.router.dispatch import ClaudeRouteAttemptError, ModelUnavailableError, dispatch


class ModelRouter:
    """Thin façade over config loading + dispatch.

    Raises ModelUnavailableError if all configured models fail.
    Raises ClaudeRouteAttemptError if config points implementation at Claude.
    Never silently falls back to Claude.
    """

    def __init__(
        self,
        config: RouterConfig | None = None,
        config_path: Path | None = None,
        log_dir: Path | None = None,
    ) -> None:
        self._config = config or load_router_config(config_path)
        self._log_dir = log_dir

    @property
    def implementation_model(self) -> str:
        return self._config.implementation_model.model

    @property
    def implementation_provider(self) -> str:
        return self._config.implementation_model.provider

    @property
    def implementation_command(self) -> str:
        return self._config.implementation_model.command

    def run(self, task_name: str, prompt: str) -> str:
        """Dispatch a task prompt to the configured implementation_model.

        Args:
            task_name: Short identifier for this task (logged).
            prompt:    Full text to send to the model via stdin.

        Returns:
            The model's text output.

        Raises:
            ModelUnavailableError:   All models unavailable.
            ClaudeRouteAttemptError: Config points implementation at Claude.
        """
        return dispatch(task_name, prompt, self._config, log_dir=self._log_dir)
