"""Dispatch an implementation task to the configured model via subprocess.

Rules enforced here:
  - The architecture model (Claude) is never used for implementation tasks.
  - If the primary model is unavailable, fallbacks from config are tried in order.
  - If all configured models fail, ModelUnavailableError is raised — no silent
    fallback to any unspecified model and especially not to Claude.
  - All attempts are logged regardless of outcome.
"""
from __future__ import annotations

import shlex
import subprocess
import time
from pathlib import Path

from src.router.config_loader import ModelEntry, RouterConfig
from src.router.router_log import make_entry, write_log_entry


class ModelUnavailableError(Exception):
    """Raised when all configured models are unreachable or fail."""


class ClaudeRouteAttemptError(Exception):
    """Raised when caller tries to route an implementation task to Claude."""


_CLAUDE_PROVIDERS = frozenset({"claude", "anthropic"})


def _run_model(
    entry: ModelEntry,
    prompt: str,
    timeout: int,
) -> str:
    """Execute `{command}` via subprocess, pipe prompt to stdin, return stdout.

    Raises subprocess.SubprocessError / subprocess.TimeoutExpired on failure.
    """
    cmd = shlex.split(entry.command)
    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise subprocess.SubprocessError(
            f"Model {entry.model!r} exited with code {result.returncode}: {stderr}"
        )
    return result.stdout


def dispatch(
    task_name: str,
    prompt: str,
    config: RouterConfig,
    log_dir: Path | None = None,
) -> str:
    """Send a task prompt to the configured implementation_model.

    Tries the primary model first, then fallbacks in order.
    Logs every attempt. Raises ModelUnavailableError if all fail.
    Never routes to Claude, even if Claude appears in the fallback chain.

    Args:
        task_name: Short label for the task (recorded in log).
        prompt:    The full text prompt to send to the model.
        config:    Parsed RouterConfig from load_router_config().
        log_dir:   Override log directory (for tests).

    Returns:
        The model's output as a string.

    Raises:
        ClaudeRouteAttemptError: If the primary model provider is Claude.
        ModelUnavailableError:   If every configured model fails.
    """
    primary = config.implementation_model

    if primary.provider.lower() in _CLAUDE_PROVIDERS:
        raise ClaudeRouteAttemptError(
            f"implementation_model provider is {primary.provider!r} (Claude). "
            "Claude must not be used for implementation tasks. "
            "Update config/models.yaml to point implementation_model at a non-Claude provider."
        )

    candidates = [primary] + list(config.fallback_order)
    last_error: str = "no candidates configured"
    fallback_used = False
    used_provider: str = primary.provider
    used_model: str = primary.model
    used_command: str = primary.command

    for i, candidate in enumerate(candidates):
        if candidate.provider.lower() in _CLAUDE_PROVIDERS:
            continue

        is_fallback = i > 0
        try:
            output = _run_model(candidate, prompt, config.timeout_seconds)
            write_log_entry(make_entry(
                task_name=task_name,
                provider=candidate.provider,
                model=candidate.model,
                command=candidate.command,
                success=True,
                fallback_used=is_fallback,
                fallback_provider=candidate.provider if is_fallback else None,
                fallback_model=candidate.model if is_fallback else None,
                output_length=len(output),
            ), log_dir=log_dir)
            return output

        except (subprocess.SubprocessError, subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
            last_error = str(exc)
            used_provider = candidate.provider
            used_model = candidate.model
            used_command = candidate.command
            if is_fallback:
                fallback_used = True

    write_log_entry(make_entry(
        task_name=task_name,
        provider=used_provider,
        model=used_model,
        command=used_command,
        success=False,
        fallback_used=fallback_used,
        error=last_error,
        output_length=0,
    ), log_dir=log_dir)

    raise ModelUnavailableError(
        f"All configured models failed for task {task_name!r}. Last error: {last_error}\n"
        "Check that ollama is running and signed in. "
        "This router does not fall back to Claude."
    )
