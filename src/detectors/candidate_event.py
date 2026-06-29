"""CandidateEvent — the structured output of every detector.

One event per detector per candle. No trading logic. No scoring.

KCU-aligned fields:
  source_status           — HYPOTHESIS / PARTIALLY_COVERED (never CONFIRMED in Phase 4A)
  reason_codes            — machine-readable stable identifiers (from kcu_candidate_contract)
  supporting_components   — KCU component names that ARE present
  required_missing_components — components required for validity but not yet determinable
  invalidating_components — conditions that would cancel the watch
  no_trade_risk           — reasons a human reviewer must NOT trade this event as-is
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from src.detectors.kcu_candidate_contract import (
    WATCH_CANDIDATE_TYPES,
    FORBIDDEN_CANDIDATE_TYPES,
    KCUSourceStatus,
)


@dataclass
class CandidateEvent:
    """A single candidate setup signal emitted by one detector for one candle.

    All Phase 4A events must have source_status in WATCH_VALUES (never CONFIRMED).
    All Phase 4A events must have candidate_type in WATCH_CANDIDATE_TYPES —
    never a confirmed or graded setup label (those belong to future phases).
    """
    # Identity
    timestamp: int
    symbol: str
    timeframe: str
    replay_date: str
    candle_index: int

    # Classification
    candidate_type: str
    source_status: str          # KCUSourceStatus.HYPOTHESIS | PARTIALLY_COVERED

    # Human-readable signal narrative
    reasons: list[str] = field(default_factory=list)

    # Machine-readable signal codes (stable identifiers for programmatic use)
    reason_codes: list[str] = field(default_factory=list)

    # Numeric measurement data that satisfied detection conditions
    supporting_features: dict[str, Any] = field(default_factory=dict)

    # KCU component names confirmed present by detector
    supporting_components: list[str] = field(default_factory=list)

    # KCU component names required for setup validity but NOT verifiable in Phase 4A
    required_missing_components: list[str] = field(default_factory=list)

    # Conditions that would cancel/invalidate this watch
    invalidating_components: list[str] = field(default_factory=list)

    # Reasons a human reviewer must NOT trade this watch as-is
    no_trade_risk: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> list[str]:
        """Return a list of validation errors. Empty list = valid."""
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

        if self.candidate_type in FORBIDDEN_CANDIDATE_TYPES:
            errors.append(
                f"candidate_type {self.candidate_type!r} is forbidden in Phase 4A — "
                f"use a WATCH variant (e.g. LTP_WATCH)"
            )
        elif self.candidate_type not in WATCH_CANDIDATE_TYPES:
            errors.append(
                f"candidate_type {self.candidate_type!r} not in "
                f"{sorted(WATCH_CANDIDATE_TYPES)}"
            )

        if self.source_status not in KCUSourceStatus.ALL_VALUES:
            errors.append(
                f"source_status {self.source_status!r} not in "
                f"{sorted(KCUSourceStatus.ALL_VALUES)}"
            )
        elif self.source_status == KCUSourceStatus.CONFIRMED:
            errors.append(
                "source_status 'CONFIRMED' is forbidden in Phase 4A — "
                "confirmation belongs to a future phase"
            )

        if not self.no_trade_risk:
            errors.append(
                "no_trade_risk must be non-empty — every Phase 4A watch "
                "must document why it cannot be traded without further review"
            )

        return errors

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "replay_date": self.replay_date,
            "candle_index": self.candle_index,
            "candidate_type": self.candidate_type,
            "source_status": self.source_status,
            "reasons": list(self.reasons),
            "reason_codes": list(self.reason_codes),
            "supporting_features": dict(self.supporting_features),
            "supporting_components": list(self.supporting_components),
            "required_missing_components": list(self.required_missing_components),
            "invalidating_components": list(self.invalidating_components),
            "no_trade_risk": list(self.no_trade_risk),
        }

    def to_jsonl_line(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CandidateEvent":
        return cls(
            timestamp=int(d["timestamp"]),
            symbol=str(d["symbol"]),
            timeframe=str(d["timeframe"]),
            replay_date=str(d["replay_date"]),
            candle_index=int(d["candle_index"]),
            candidate_type=str(d["candidate_type"]),
            source_status=str(d["source_status"]),
            reasons=list(d.get("reasons", [])),
            reason_codes=list(d.get("reason_codes", [])),
            supporting_features=dict(d.get("supporting_features", {})),
            supporting_components=list(d.get("supporting_components", [])),
            required_missing_components=list(d.get("required_missing_components", [])),
            invalidating_components=list(d.get("invalidating_components", [])),
            no_trade_risk=list(d.get("no_trade_risk", [])),
        )
