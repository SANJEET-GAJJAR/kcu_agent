"""Scenario watch events — pre-confirmation, non-trading confluence records.

These records are intentionally watch-only. They do not contain entries,
stops, targets, position sizing, or trade outcomes.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from src.detectors.kcu_candidate_contract import KCUSourceStatus


class ScenarioType:
    BOUNCE_WATCH = "BOUNCE_WATCH"
    REJECTION_WATCH = "REJECTION_WATCH"
    LTP_CONTINUATION_WATCH = "LTP_CONTINUATION_WATCH"

    ALL_VALUES: frozenset[str] = frozenset({
        BOUNCE_WATCH,
        REJECTION_WATCH,
        LTP_CONTINUATION_WATCH,
    })


class ScenarioConfidence:
    WATCH = "WATCH"
    ALL_VALUES: frozenset[str] = frozenset({WATCH})


@dataclass
class ScenarioEvent:
    """One deterministic watch-only scenario candidate."""

    timestamp: int
    symbol: str
    timeframe: str
    replay_date: str
    candle_index: int

    scenario_type: str
    approaching_levels: list[str] = field(default_factory=list)
    confluence_count: int = 0
    distance_to_zone: float | None = None
    required_confirmation: list[str] = field(default_factory=list)
    invalidation_hint: str = ""
    confidence: str = ScenarioConfidence.WATCH
    source_status: str = KCUSourceStatus.HYPOTHESIS

    detector_labels: list[str] = field(default_factory=list)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.timestamp <= 0:
            errors.append(f"timestamp must be > 0, got {self.timestamp}")
        if not self.symbol:
            errors.append("symbol must not be empty")
        if not self.timeframe:
            errors.append("timeframe must not be empty")
        if not self.replay_date:
            errors.append("replay_date must not be empty")
        if self.candle_index < 0:
            errors.append(f"candle_index must be >= 0, got {self.candle_index}")
        if self.scenario_type not in ScenarioType.ALL_VALUES:
            errors.append(
                f"scenario_type {self.scenario_type!r} not in "
                f"{sorted(ScenarioType.ALL_VALUES)}"
            )
        if self.confidence not in ScenarioConfidence.ALL_VALUES:
            errors.append(
                f"confidence {self.confidence!r} not in "
                f"{sorted(ScenarioConfidence.ALL_VALUES)}"
            )
        if self.source_status != KCUSourceStatus.HYPOTHESIS:
            errors.append(
                "Scenario watch layer is watch-only: source_status must be "
                f"{KCUSourceStatus.HYPOTHESIS!r}, got {self.source_status!r}"
            )
        if self.confluence_count < 0:
            errors.append(f"confluence_count must be >= 0, got {self.confluence_count}")
        if self.confluence_count != len(self.approaching_levels):
            errors.append(
                "confluence_count must equal len(approaching_levels), got "
                f"{self.confluence_count} vs {len(self.approaching_levels)}"
            )
        if self.distance_to_zone is not None and self.distance_to_zone < 0:
            errors.append(
                f"distance_to_zone must be >= 0 when provided, got {self.distance_to_zone}"
            )
        if not self.required_confirmation:
            errors.append("required_confirmation must be non-empty")
        if not self.invalidation_hint:
            errors.append("invalidation_hint must be non-empty")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "replay_date": self.replay_date,
            "candle_index": self.candle_index,
            "scenario_type": self.scenario_type,
            "approaching_levels": list(self.approaching_levels),
            "confluence_count": self.confluence_count,
            "distance_to_zone": self.distance_to_zone,
            "required_confirmation": list(self.required_confirmation),
            "invalidation_hint": self.invalidation_hint,
            "confidence": self.confidence,
            "source_status": self.source_status,
            "detector_labels": list(self.detector_labels),
        }

    def to_jsonl_line(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ScenarioEvent":
        return cls(
            timestamp=int(d["timestamp"]),
            symbol=str(d["symbol"]),
            timeframe=str(d["timeframe"]),
            replay_date=str(d["replay_date"]),
            candle_index=int(d["candle_index"]),
            scenario_type=str(d["scenario_type"]),
            approaching_levels=list(d.get("approaching_levels", [])),
            confluence_count=int(d.get("confluence_count", 0)),
            distance_to_zone=(
                float(d["distance_to_zone"])
                if d.get("distance_to_zone") is not None else None
            ),
            required_confirmation=list(d.get("required_confirmation", [])),
            invalidation_hint=str(d.get("invalidation_hint", "")),
            confidence=str(d.get("confidence", ScenarioConfidence.WATCH)),
            source_status=str(d.get("source_status", KCUSourceStatus.HYPOTHESIS)),
            detector_labels=list(d.get("detector_labels", [])),
        )
