"""TradePlan — hypothetical trade plan derived from a CONFIRMED_SETUP event.

Phase 5A: plan construction only.
No outcome simulation. No win/loss tracking. No position sizing.
No performance statistics. No AI reasoning.

A TradePlan is always produced from a ConfirmationEvent (Phase 4B output).
It may be VALID or one of several REJECTED statuses depending on whether
all required fields can be derived from the eval candle's feature data.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


class TradePlanDirection:
    """Direction of the hypothetical trade."""
    LONG = "long"
    SHORT = "short"
    UNKNOWN = "unknown"
    ALL_VALUES: frozenset[str] = frozenset({"long", "short", "unknown"})


class PlanStatus:
    """Why a TradePlan was accepted or rejected."""
    VALID = "VALID"
    REJECTED_NOT_CONFIRMED = "REJECTED_NOT_CONFIRMED"
    REJECTED_UNSUPPORTED_TYPE = "REJECTED_UNSUPPORTED_TYPE"
    REJECTED_NOT_TRADABLE = "REJECTED_NOT_TRADABLE"
    REJECTED_EVENT_FEATURE_MISMATCH = "REJECTED_EVENT_FEATURE_MISMATCH"
    REJECTED_MISSING_FIELDS = "REJECTED_MISSING_FIELDS"
    REJECTED_RR_BELOW_MINIMUM = "REJECTED_RR_BELOW_MINIMUM"
    ALL_VALUES: frozenset[str] = frozenset({
        "VALID",
        "REJECTED_NOT_CONFIRMED",
        "REJECTED_UNSUPPORTED_TYPE",
        "REJECTED_NOT_TRADABLE",
        "REJECTED_EVENT_FEATURE_MISMATCH",
        "REJECTED_MISSING_FIELDS",
        "REJECTED_RR_BELOW_MINIMUM",
    })


@dataclass
class TradePlan:
    """A hypothetical trade plan built from a confirmed setup.

    Fields are None when the value could not be determined.
    None is explicit UNKNOWN — never inferred or guessed.

    No outcome fields exist in this dataclass.
    Win/loss tracking belongs to a future phase.
    """
    # --- Identity ---
    plan_id: str                  # deterministic: {symbol}_{date}_{candle_index:05d}
    timestamp: int                # eval candle timestamp
    symbol: str
    timeframe: str
    replay_date: str
    candle_index: int             # eval candle index (where confirmation was assessed)

    # --- Setup origin ---
    setup_type: str               # e.g. "CHOP", "FAILED_LTP"
    watch_type: str               # e.g. "CHOP", "FAILED_LTP_WATCH"
    grade: str | None             # "A" | "B" | "C" | None (only CONFIRMED_SETUP has grade)
    source_candle_index: int      # the original WATCH candle index

    # --- Trade parameters ---
    direction: str                # TradePlanDirection: "long" | "short" | "unknown"
    entry_trigger: float | None   # price at which trade is entered (close of eval candle)
    stop: float | None            # stop loss price
    risk: float | None            # abs(entry - stop)
    target_1_5r: float | None     # 1.5 * risk from entry in trade direction
    reward_risk: float | None     # target_r (always config.target_r when valid)
    invalidation: str             # human-readable condition that cancels the plan

    # --- Plan validity ---
    plan_status: str              # PlanStatus value
    rejection_reason: str | None  # None for VALID; required for all rejected statuses

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def is_valid(self) -> bool:
        return self.plan_status == PlanStatus.VALID

    def validate(self) -> list[str]:
        """Return a list of validation errors. Empty = valid."""
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
        if self.source_candle_index < 0:
            errors.append(f"source_candle_index must be >= 0, got {self.source_candle_index}")

        if self.direction not in TradePlanDirection.ALL_VALUES:
            errors.append(
                f"direction {self.direction!r} not in "
                f"{sorted(TradePlanDirection.ALL_VALUES)}"
            )

        if self.plan_status not in PlanStatus.ALL_VALUES:
            errors.append(
                f"plan_status {self.plan_status!r} not in "
                f"{sorted(PlanStatus.ALL_VALUES)}"
            )

        if self.plan_status == PlanStatus.VALID:
            if self.direction not in (TradePlanDirection.LONG, TradePlanDirection.SHORT):
                errors.append(
                    f"VALID plan must have long or short direction, "
                    f"got {self.direction!r}"
                )
            if self.entry_trigger is None:
                errors.append("VALID plan must have entry_trigger")
            if self.stop is None:
                errors.append("VALID plan must have stop")
            if self.risk is None:
                errors.append("VALID plan must have risk")
            if self.target_1_5r is None:
                errors.append("VALID plan must have target_1_5r")
            if self.reward_risk is None:
                errors.append("VALID plan must have reward_risk")

        if self.plan_status != PlanStatus.VALID and self.rejection_reason is None:
            errors.append(
                "rejected plan must have a rejection_reason; "
                f"got plan_status={self.plan_status!r} with rejection_reason=None"
            )

        return errors

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "replay_date": self.replay_date,
            "candle_index": self.candle_index,
            "setup_type": self.setup_type,
            "watch_type": self.watch_type,
            "grade": self.grade,
            "source_candle_index": self.source_candle_index,
            "direction": self.direction,
            "entry_trigger": self.entry_trigger,
            "stop": self.stop,
            "risk": self.risk,
            "target_1_5r": self.target_1_5r,
            "reward_risk": self.reward_risk,
            "invalidation": self.invalidation,
            "plan_status": self.plan_status,
            "rejection_reason": self.rejection_reason,
        }

    def to_jsonl_line(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TradePlan":
        return cls(
            plan_id=str(d["plan_id"]),
            timestamp=int(d["timestamp"]),
            symbol=str(d["symbol"]),
            timeframe=str(d["timeframe"]),
            replay_date=str(d["replay_date"]),
            candle_index=int(d["candle_index"]),
            setup_type=str(d["setup_type"]),
            watch_type=str(d["watch_type"]),
            grade=d.get("grade"),
            source_candle_index=int(d["source_candle_index"]),
            direction=str(d["direction"]),
            entry_trigger=float(d["entry_trigger"]) if d.get("entry_trigger") is not None else None,
            stop=float(d["stop"]) if d.get("stop") is not None else None,
            risk=float(d["risk"]) if d.get("risk") is not None else None,
            target_1_5r=float(d["target_1_5r"]) if d.get("target_1_5r") is not None else None,
            reward_risk=float(d["reward_risk"]) if d.get("reward_risk") is not None else None,
            invalidation=str(d["invalidation"]),
            plan_status=str(d["plan_status"]),
            rejection_reason=d.get("rejection_reason"),
        )
