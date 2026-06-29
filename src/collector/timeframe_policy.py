"""Timeframe policy — validates that all required candle collections exist before the pipeline runs.

The KCU protocol uses different timeframes for different parts of the trading session:
  - 09:30–10:00 ET: 2m candles (open range)
  - 10:00–16:00 ET: 5m candles (main session)

Both must be independently collected from TradingView replay.
Derivation of 5m from 2m is never permitted.

Two protocol levels are defined:
  - smoke_test:    2m only — verifies collection infrastructure
  - full_protocol: 2m + 5m — required for a real KCU backtest run

Usage:
    policy = load_timeframe_policy()
    result = validate_protocol_readiness("TSLA", "2026-06-22", Path("outputs/candles"))
    if not result.ready:
        raise ProtocolReadinessError(result.summary())
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)

_DEFAULT_POLICY_PATH = (
    Path(__file__).parents[2] / "config" / "timeframe_policy.yaml"
)

_CANDLE_OUTPUT_DIR = Path(__file__).parents[2] / "outputs" / "candles"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ProtocolReadinessError(Exception):
    """Raised when required timeframe collections are missing or invalid.

    Prevents the full KCU pipeline from running without all required data.
    """


class TimeframePolicyConfigError(Exception):
    """Raised when the timeframe policy config is malformed."""


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class TimeframeWindow:
    start: str      # ET time "HH:MM"
    end: str        # ET time "HH:MM"
    timeframe: str  # e.g. "2", "5", "10"
    label: str      # human label, e.g. "open_range"


@dataclass
class TimeframePolicyConfig:
    version: str
    policy_name: str
    windows: list[TimeframeWindow]
    required_timeframes: dict[str, list[str]]   # {"full_protocol": ["2","5"], "smoke_test": ["2"]}
    allow_derived_timeframes: bool

    def __post_init__(self) -> None:
        if not self.version:
            raise TimeframePolicyConfigError("version must not be empty")
        if not self.windows:
            raise TimeframePolicyConfigError("default_policy.windows must not be empty")
        if not self.required_timeframes:
            raise TimeframePolicyConfigError("required_timeframes must not be empty")
        if self.allow_derived_timeframes:
            raise TimeframePolicyConfigError(
                "allow_derived_timeframes=true is not supported. "
                "All timeframes must be independently collected."
            )
        known_levels = {"full_protocol", "smoke_test"}
        for level in self.required_timeframes:
            if level not in known_levels:
                raise TimeframePolicyConfigError(
                    f"Unknown protocol level {level!r}. Valid: {sorted(known_levels)}"
                )

    def required_for(self, level: str) -> list[str]:
        """Return required timeframe strings for the given protocol level."""
        if level not in self.required_timeframes:
            raise TimeframePolicyConfigError(
                f"Unknown protocol level {level!r}. "
                f"Valid: {sorted(self.required_timeframes)}"
            )
        return list(self.required_timeframes[level])


def load_timeframe_policy(path: Path | str | None = None) -> TimeframePolicyConfig:
    """Load TimeframePolicyConfig from timeframe_policy.yaml."""
    config_path = Path(path) if path else _DEFAULT_POLICY_PATH
    with open(config_path) as f:
        data = yaml.safe_load(f)

    policy_data = data.get("default_policy", {})
    windows = [
        TimeframeWindow(
            start=str(w["start"]),
            end=str(w["end"]),
            timeframe=str(w["timeframe"]),
            label=str(w.get("label", "")),
        )
        for w in policy_data.get("windows", [])
    ]

    raw_required = data.get("required_timeframes", {})
    required_timeframes = {
        level: [str(tf) for tf in tfs]
        for level, tfs in raw_required.items()
    }

    return TimeframePolicyConfig(
        version=str(data.get("version", "")),
        policy_name=str(policy_data.get("name", "unknown")),
        windows=windows,
        required_timeframes=required_timeframes,
        allow_derived_timeframes=bool(data.get("allow_derived_timeframes", False)),
    )


# ---------------------------------------------------------------------------
# Collection path helpers
# ---------------------------------------------------------------------------

def collection_path(ticker: str, date: str, timeframe: str, output_dir: Path) -> Path:
    """Return the canonical JSONL path for a collection."""
    tf_label = f"{timeframe}m" if not timeframe.endswith("m") else timeframe
    return output_dir / f"{ticker.upper()}_{date}_{tf_label}.jsonl"


def preflight_companion_path(collection: Path) -> Path:
    """Return the preflight companion JSON path for a collection JSONL."""
    return collection.with_name(collection.stem + "_preflight.json")


# ---------------------------------------------------------------------------
# Readiness result
# ---------------------------------------------------------------------------

@dataclass
class CollectionStatus:
    timeframe: str
    collection_path: Path
    exists: bool
    preflight_companion_exists: bool
    preflight_passed: bool
    missing_reason: str = ""   # empty when fully valid


@dataclass
class ProtocolReadinessResult:
    ticker: str
    date: str
    protocol_level: str
    required_timeframes: list[str]
    statuses: list[CollectionStatus] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return all(s.exists and s.preflight_passed for s in self.statuses)

    @property
    def missing(self) -> list[CollectionStatus]:
        return [s for s in self.statuses if not (s.exists and s.preflight_passed)]

    def summary(self) -> str:
        if self.ready:
            return (
                f"{self.ticker} {self.date} [{self.protocol_level}]: "
                f"all {len(self.statuses)} required collections present and valid"
            )
        lines = [
            f"{self.ticker} {self.date} [{self.protocol_level}]: "
            f"protocol readiness FAILED — {len(self.missing)}/{len(self.statuses)} collection(s) missing or invalid:"
        ]
        for s in self.missing:
            lines.append(f"  ✗ {s.timeframe}m: {s.missing_reason} ({s.collection_path.name})")
        for s in self.statuses:
            if s.exists and s.preflight_passed:
                lines.append(f"  ✓ {s.timeframe}m: present and valid")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

def validate_protocol_readiness(
    ticker: str,
    date: str,
    output_dir: Path,
    protocol_level: str = "full_protocol",
    policy: TimeframePolicyConfig | None = None,
) -> ProtocolReadinessResult:
    """Check that all required timeframe collections exist and passed preflight.

    Args:
        ticker:         Ticker symbol, e.g. "TSLA".
        date:           ISO date string, e.g. "2026-06-22".
        output_dir:     Directory containing JSONL collection files.
        protocol_level: "full_protocol" (requires all policy timeframes) or
                        "smoke_test" (requires 2m only).
        policy:         Loaded policy config. If None, loads from default path.

    Returns:
        ProtocolReadinessResult. Check .ready to determine if pipeline may proceed.
    """
    if policy is None:
        policy = load_timeframe_policy()

    required_tfs = policy.required_for(protocol_level)
    statuses: list[CollectionStatus] = []

    for tf in required_tfs:
        coll_path = collection_path(ticker, date, tf, output_dir)
        companion = preflight_companion_path(coll_path)

        if not coll_path.exists():
            statuses.append(CollectionStatus(
                timeframe=tf,
                collection_path=coll_path,
                exists=False,
                preflight_companion_exists=False,
                preflight_passed=False,
                missing_reason=f"collection file not found",
            ))
            continue

        if not companion.exists():
            statuses.append(CollectionStatus(
                timeframe=tf,
                collection_path=coll_path,
                exists=True,
                preflight_companion_exists=False,
                preflight_passed=False,
                missing_reason="preflight companion file missing",
            ))
            continue

        try:
            import json
            companion_data = json.loads(companion.read_text())
        except Exception as exc:
            statuses.append(CollectionStatus(
                timeframe=tf,
                collection_path=coll_path,
                exists=True,
                preflight_companion_exists=True,
                preflight_passed=False,
                missing_reason=f"preflight companion corrupt: {exc}",
            ))
            continue

        passed = companion_data.get("preflight_passed") is True
        if not passed:
            reasons = companion_data.get("failure_reasons", [])
            statuses.append(CollectionStatus(
                timeframe=tf,
                collection_path=coll_path,
                exists=True,
                preflight_companion_exists=True,
                preflight_passed=False,
                missing_reason=f"preflight_passed=False: {reasons}",
            ))
            continue

        statuses.append(CollectionStatus(
            timeframe=tf,
            collection_path=coll_path,
            exists=True,
            preflight_companion_exists=True,
            preflight_passed=True,
        ))

    result = ProtocolReadinessResult(
        ticker=ticker,
        date=date,
        protocol_level=protocol_level,
        required_timeframes=required_tfs,
        statuses=statuses,
    )

    log.info("Protocol readiness [%s] %s %s: %s", protocol_level, ticker, date,
             "READY" if result.ready else "NOT READY")
    return result


def require_protocol_ready(
    ticker: str,
    date: str,
    output_dir: Path,
    protocol_level: str = "full_protocol",
    policy: TimeframePolicyConfig | None = None,
) -> ProtocolReadinessResult:
    """Assert protocol readiness — raises ProtocolReadinessError if not ready.

    Call this before starting the full KCU pipeline to ensure all required
    timeframe collections are present and have passed preflight.

    Raises:
        ProtocolReadinessError: If any required collection is missing or invalid.
    """
    result = validate_protocol_readiness(ticker, date, output_dir, protocol_level, policy)
    if not result.ready:
        raise ProtocolReadinessError(result.summary())
    return result
