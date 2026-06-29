"""ConfirmationEvent — the output of the Phase 4B confirmation engine.

One event per evaluated WATCH candidate. Outcome is CONFIRMED_SETUP or
REJECTED_SETUP. No entry, stop, target, sizing, outcome statistics, or
trade management fields exist in this module.

Phase 4B contract:
  - CONFIRMED_SETUP requires source_status=CONFIRMED and a grade.
  - REJECTED_SETUP never carries a grade.
  - Both outcomes document all component checks for audit traceability.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from src.detectors.kcu_candidate_contract import KCUSourceStatus


class ConfirmationOutcome:
    CONFIRMED_SETUP = "CONFIRMED_SETUP"
    REJECTED_SETUP = "REJECTED_SETUP"
    ALL_VALUES: frozenset[str] = frozenset({"CONFIRMED_SETUP", "REJECTED_SETUP"})


class ConfirmationReasonCode:
    LEVEL_CONTEXT_UNVERIFIED = "LEVEL_CONTEXT_UNVERIFIED"
    TREND_CONTEXT_UNVERIFIED = "TREND_CONTEXT_UNVERIFIED"
    DIRECTIONAL_CONTEXT_UNVERIFIED = "DIRECTIONAL_CONTEXT_UNVERIFIED"
    ALL_COMPONENTS_VERIFIED = "ALL_COMPONENTS_VERIFIED"
    NO_INVALIDATING_COMPONENT = "NO_INVALIDATING_COMPONENT"
    DECISIVE_DIRECTIONAL_BREAK = "DECISIVE_DIRECTIONAL_BREAK"
    DIRECTIONAL_RANGE_EXPANSION = "DIRECTIONAL_RANGE_EXPANSION"
    CONFIRMATION_WINDOW_EXPIRED = "CONFIRMATION_WINDOW_EXPIRED"


SETUP_TYPE_MAP: dict[str, str] = {
    "LTP_WATCH": "LTP",
    "REJECTION_WATCH": "REJECTION",
    "REVERSAL_WATCH": "REVERSAL",
    "BOUNCE_WATCH": "BOUNCE",
    "FAILED_LTP_WATCH": "FAILED_LTP",
    "CHOP": "CHOP",
}

VALID_GRADES: frozenset[str] = frozenset({"A", "B", "C"})


@dataclass
class ConfirmationEvent:
    """The result of evaluating one WATCH candidate against KCU confirmation criteria.

    No entry, stop, target, sizing, or trade management fields.
    All required KCU components are documented for human review.
    """
    # Origin: the watch candle being evaluated
    timestamp: int
    symbol: str
    timeframe: str
    replay_date: str
    candle_index: int

    # Where confirmation was evaluated (the candle used for invalidation checks)
    evaluated_at_candle_index: int
    evaluated_at_timestamp: int

    # Classification
    watch_type: str          # original WATCH type, e.g. "LTP_WATCH"
    setup_type: str          # human label, e.g. "LTP"
    outcome: str             # ConfirmationOutcome.CONFIRMED_SETUP | REJECTED_SETUP
    grade: str | None        # "A" | "B" | "C" — CONFIRMED_SETUP only; None for REJECTED
    source_status: str       # CONFIRMED if outcome=CONFIRMED_SETUP; else original WATCH status

    # Component audit
    confirmed_components: list[str] = field(default_factory=list)
    missing_components: list[str] = field(default_factory=list)
    invalidating_components: list[str] = field(default_factory=list)

    # Narrative
    reasons: list[str] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)

    # Traceability back to the originating WATCH candidate
    candidate_candle_index: int = 0
    candidate_timestamp: int = 0
    candidate_reason_codes: list[str] = field(default_factory=list)

    def validate(self) -> list[str]:
        """Return list of validation errors. Empty list = valid."""
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
        if self.evaluated_at_candle_index < 0:
            errors.append(f"evaluated_at_candle_index must be >= 0")

        if self.outcome not in ConfirmationOutcome.ALL_VALUES:
            errors.append(
                f"outcome {self.outcome!r} not in "
                f"{sorted(ConfirmationOutcome.ALL_VALUES)}"
            )

        if self.source_status not in KCUSourceStatus.ALL_VALUES:
            errors.append(f"source_status {self.source_status!r} is invalid")

        if self.outcome == ConfirmationOutcome.CONFIRMED_SETUP:
            if self.source_status != KCUSourceStatus.CONFIRMED:
                errors.append(
                    "CONFIRMED_SETUP must have source_status=CONFIRMED, "
                    f"got {self.source_status!r}"
                )
            if self.grade not in VALID_GRADES:
                errors.append(
                    f"CONFIRMED_SETUP must have grade in {sorted(VALID_GRADES)}, "
                    f"got {self.grade!r}"
                )

        if self.outcome == ConfirmationOutcome.REJECTED_SETUP:
            if self.grade is not None:
                errors.append(
                    f"REJECTED_SETUP must not carry a grade, got {self.grade!r}"
                )

        if not self.reasons:
            errors.append("reasons must be non-empty")

        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "replay_date": self.replay_date,
            "candle_index": self.candle_index,
            "evaluated_at_candle_index": self.evaluated_at_candle_index,
            "evaluated_at_timestamp": self.evaluated_at_timestamp,
            "watch_type": self.watch_type,
            "setup_type": self.setup_type,
            "outcome": self.outcome,
            "grade": self.grade,
            "source_status": self.source_status,
            "confirmed_components": list(self.confirmed_components),
            "missing_components": list(self.missing_components),
            "invalidating_components": list(self.invalidating_components),
            "reasons": list(self.reasons),
            "reason_codes": list(self.reason_codes),
            "candidate_candle_index": self.candidate_candle_index,
            "candidate_timestamp": self.candidate_timestamp,
            "candidate_reason_codes": list(self.candidate_reason_codes),
        }

    def to_jsonl_line(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ConfirmationEvent":
        return cls(
            timestamp=int(d["timestamp"]),
            symbol=str(d["symbol"]),
            timeframe=str(d["timeframe"]),
            replay_date=str(d["replay_date"]),
            candle_index=int(d["candle_index"]),
            evaluated_at_candle_index=int(d["evaluated_at_candle_index"]),
            evaluated_at_timestamp=int(d["evaluated_at_timestamp"]),
            watch_type=str(d["watch_type"]),
            setup_type=str(d["setup_type"]),
            outcome=str(d["outcome"]),
            grade=d.get("grade"),
            source_status=str(d["source_status"]),
            confirmed_components=list(d.get("confirmed_components", [])),
            missing_components=list(d.get("missing_components", [])),
            invalidating_components=list(d.get("invalidating_components", [])),
            reasons=list(d.get("reasons", [])),
            reason_codes=list(d.get("reason_codes", [])),
            candidate_candle_index=int(d.get("candidate_candle_index", 0)),
            candidate_timestamp=int(d.get("candidate_timestamp", 0)),
            candidate_reason_codes=list(d.get("candidate_reason_codes", [])),
        )
