"""Workspace preflight — protect the live trading workspace from backtesting actions.

The collector must NEVER touch the live trading layout.  This module verifies
the active TradingView layout/workspace is the dedicated backtesting layout
before any destructive action (ticker change, timeframe change, replay start,
template load) is allowed.

Decision matrix:
    detected == backtest workspace   → PASS
    detected == live workspace       → FAIL (always, regardless of override flag)
    detected == unknown              → FAIL if allow_unknown_workspace_for_collection=False
                                     → WARN (pass with warning) if override=True

All outcomes are recorded in WorkspacePreflightResult and persisted to the
collection metadata.

Config is loaded from config/workspace.yaml via load_workspace_config().
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)

_DEFAULT_WORKSPACE_CONFIG_PATH = (
    Path(__file__).parents[2] / "config" / "workspace.yaml"
)

_LAYOUT_DETECTION_TOOL = "layout_get_current"
_LAYOUT_LIST_TOOL = "layout_list"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class WorkspacePreflightError(Exception):
    """Raised when workspace preflight fails — collection must not proceed.

    Possible causes:
    - Active layout is the protected live trading workspace.
    - Active layout could not be detected and allow_unknown_workspace_for_collection=False.
    - workspace.yaml is misconfigured (empty workspace names).
    """


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class WorkspaceConfig:
    """Loaded from config/workspace.yaml."""
    live_workspace_name: str
    backtest_workspace_name: str
    required_workspace: str                    # always "backtesting"
    protected_live_workspace: bool             # always True in production
    allow_unknown_workspace_for_collection: bool  # False by default

    def __post_init__(self) -> None:
        if not self.live_workspace_name:
            raise ValueError("live_workspace_name must not be empty in workspace.yaml")
        if not self.backtest_workspace_name:
            raise ValueError("backtest_workspace_name must not be empty in workspace.yaml")
        if self.required_workspace != "backtesting":
            raise ValueError(
                f"required_workspace must be 'backtesting', got {self.required_workspace!r}"
            )


def load_workspace_config(
    path: Path | str | None = None,
) -> WorkspaceConfig:
    """Load WorkspaceConfig from workspace.yaml."""
    config_path = Path(path) if path else _DEFAULT_WORKSPACE_CONFIG_PATH
    with open(config_path) as f:
        data = yaml.safe_load(f)

    return WorkspaceConfig(
        live_workspace_name=str(data["live_workspace_name"]),
        backtest_workspace_name=str(data["backtest_workspace_name"]),
        required_workspace=str(data.get("required_workspace", "backtesting")),
        protected_live_workspace=bool(data.get("protected_live_workspace", True)),
        allow_unknown_workspace_for_collection=bool(
            data.get("allow_unknown_workspace_for_collection", False)
        ),
    )


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class WorkspacePreflightResult:
    """Result of one workspace preflight check."""
    workspace_name: str | None      # detected layout name, or None if unknown
    workspace_verified: bool        # True only when backtest workspace confirmed
    live_workspace_protected: bool  # always True (from config)
    workspace_warning: str | None   # warning message if override used
    passed: bool
    failure_reason: str | None = None

    def to_metadata(self) -> dict[str, Any]:
        """Subset persisted into collection metadata."""
        return {
            "workspace_name": self.workspace_name or "unknown",
            "workspace_verified": self.workspace_verified,
            "live_workspace_protected": self.live_workspace_protected,
            "workspace_warning": self.workspace_warning,
            "workspace_preflight_passed": self.passed,
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------

class WorkspacePreflight:
    """Verify the active TradingView workspace before any destructive collection action.

    Usage:
        config = load_workspace_config()
        preflight = WorkspacePreflight(config)
        result = await preflight.run(client)
        # WorkspacePreflightError is raised on failure — collection must not proceed.
    """

    def __init__(self, config: WorkspaceConfig) -> None:
        self._config = config

    async def run(self, client: Any) -> WorkspacePreflightResult:
        """Run workspace preflight.  Raises WorkspacePreflightError on failure.

        Args:
            client: TradingViewClient instance (must have call_tool()).

        Returns:
            WorkspacePreflightResult with full detection details.

        Raises:
            WorkspacePreflightError: active workspace is live, or unknown and
                                     allow_unknown_workspace_for_collection=False.
        """
        cfg = self._config
        detected_name: str | None = None
        detection_source: str | None = None

        try:
            result = await client.call_tool(_LAYOUT_DETECTION_TOOL, {})
            if isinstance(result, dict):
                detected_name = result.get("layout_name") or None
                detection_source = result.get("detection_source") or None
        except Exception as exc:
            log.warning("layout_get_current failed: %s", exc)

        # Fallback: if DOM detection returned null, try layout_list.
        # If exactly one saved layout exists and its name matches the backtest workspace,
        # it must be the active layout (TradingView Desktop loads the last-used layout).
        if detected_name is None:
            try:
                ll_result = await client.call_tool(_LAYOUT_LIST_TOOL, {})
                if isinstance(ll_result, dict):
                    layouts = ll_result.get("layouts") or []
                    backtest_lower = cfg.backtest_workspace_name.lower().strip()
                    live_lower = cfg.live_workspace_name.lower().strip()
                    matching = [
                        l for l in layouts
                        if isinstance(l, dict)
                        and l.get("name", "")
                        and (
                            backtest_lower in l["name"].lower()
                            or l["name"].lower() in backtest_lower
                        )
                    ]
                    live_matches = [
                        l for l in layouts
                        if isinstance(l, dict)
                        and l.get("name", "")
                        and (
                            live_lower in l["name"].lower()
                            or l["name"].lower() in live_lower
                        )
                    ]
                    if len(matching) == 1 and not live_matches:
                        detected_name = matching[0]["name"]
                        detection_source = "layout_list_single_match"
                        log.info(
                            "layout_get_current returned null; "
                            "layout_list fallback found backtest layout: %r",
                            detected_name,
                        )
            except Exception as exc:
                log.warning("layout_list fallback failed: %s", exc)

        # Normalise to lowercase for comparison
        detected_lower = detected_name.lower().strip() if detected_name else None
        live_lower = cfg.live_workspace_name.lower().strip()
        backtest_lower = cfg.backtest_workspace_name.lower().strip()

        is_live = detected_lower is not None and (
            detected_lower == live_lower
            or live_lower in detected_lower
            or detected_lower in live_lower
        )
        is_backtest = detected_lower is not None and (
            detected_lower == backtest_lower
            or backtest_lower in detected_lower
            or detected_lower in backtest_lower
        )
        is_unknown = detected_lower is None

        log.info(
            "Workspace preflight: detected=%r source=%s is_live=%s is_backtest=%s is_unknown=%s",
            detected_name, detection_source, is_live, is_backtest, is_unknown,
        )

        # --- Decision ---

        # Rule 1: Live workspace always blocked, no override.
        if is_live:
            reason = (
                f"Active layout {detected_name!r} matches the protected live trading "
                f"workspace {cfg.live_workspace_name!r}. "
                "Switch to the backtesting layout before collecting."
            )
            result_obj = WorkspacePreflightResult(
                workspace_name=detected_name,
                workspace_verified=False,
                live_workspace_protected=True,
                workspace_warning=None,
                passed=False,
                failure_reason=reason,
            )
            raise WorkspacePreflightError(reason)

        # Rule 2: Backtesting workspace confirmed.
        if is_backtest:
            return WorkspacePreflightResult(
                workspace_name=detected_name,
                workspace_verified=True,
                live_workspace_protected=True,
                workspace_warning=None,
                passed=True,
            )

        # Rule 3: Unknown workspace.
        if is_unknown:
            if not cfg.allow_unknown_workspace_for_collection:
                reason = (
                    "Active TradingView layout could not be detected (layout_get_current "
                    "returned null). Cannot verify the backtesting workspace is active. "
                    "Set allow_unknown_workspace_for_collection: true in config/workspace.yaml "
                    "to override (writes a warning into collection metadata)."
                )
                raise WorkspacePreflightError(reason)
            else:
                warning = (
                    "Workspace detection returned unknown — layout_get_current could not "
                    "identify the active layout. Collection proceeded with override "
                    "(allow_unknown_workspace_for_collection=true). "
                    "Verify manually that the backtesting layout is active."
                )
                log.warning(warning)
                return WorkspacePreflightResult(
                    workspace_name=None,
                    workspace_verified=False,
                    live_workspace_protected=True,
                    workspace_warning=warning,
                    passed=True,
                )

        # Rule 4: Detected but neither live nor backtest (some other layout).
        reason = (
            f"Active layout {detected_name!r} is neither the configured backtesting "
            f"workspace {cfg.backtest_workspace_name!r} nor the live workspace "
            f"{cfg.live_workspace_name!r}. Switch to the backtesting layout."
        )
        if not cfg.allow_unknown_workspace_for_collection:
            raise WorkspacePreflightError(reason)
        else:
            warning = (
                f"Active layout {detected_name!r} is not the configured backtesting "
                f"workspace. Collection proceeded with override "
                f"(allow_unknown_workspace_for_collection=true)."
            )
            log.warning(warning)
            return WorkspacePreflightResult(
                workspace_name=detected_name,
                workspace_verified=False,
                live_workspace_protected=True,
                workspace_warning=warning,
                passed=True,
            )
