"""Append-only router log — records every dispatch attempt."""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

_DEFAULT_LOG_DIR = Path(__file__).parents[2] / "outputs" / "model_router"


@dataclass
class RouterLogEntry:
    timestamp: float
    task_name: str
    provider: str
    model: str
    command: str
    success: bool
    fallback_used: bool
    fallback_provider: str | None
    fallback_model: str | None
    error: str | None
    output_length: int


def write_log_entry(entry: RouterLogEntry, log_dir: Path | None = None) -> Path:
    """Append entry to outputs/model_router/router_log.jsonl. Returns log path."""
    target = (log_dir or _DEFAULT_LOG_DIR) / "router_log.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a") as f:
        f.write(json.dumps(asdict(entry), separators=(",", ":")) + "\n")
    return target


def make_entry(
    *,
    task_name: str,
    provider: str,
    model: str,
    command: str,
    success: bool,
    fallback_used: bool = False,
    fallback_provider: str | None = None,
    fallback_model: str | None = None,
    error: str | None = None,
    output_length: int = 0,
) -> RouterLogEntry:
    return RouterLogEntry(
        timestamp=time.time(),
        task_name=task_name,
        provider=provider,
        model=model,
        command=command,
        success=success,
        fallback_used=fallback_used,
        fallback_provider=fallback_provider,
        fallback_model=fallback_model,
        error=error,
        output_length=output_length,
    )
