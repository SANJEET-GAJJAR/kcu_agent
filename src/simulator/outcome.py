"""Outcome result model for Phase 5B deterministic simulation."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from src.simulator.execution_contract import ExecutionOutcome


@dataclass
class OutcomeResult:
    """Terminal outcome for one simulated TradePlan.

    This is the persisted/auditable result of running one valid or rejected
    TradePlan through the Phase 5B deterministic simulator.
    """

    plan_id: str
    symbol: str
    timeframe: str
    replay_date: str
    entry_candle_index: int
    entry_timestamp: int

    exit_candle_index: int | None
    exit_timestamp: int | None
    exit_price: float | None

    exit_reason: str
    realized_r: float | None
    outcome_status: str
    counts_as_win: bool
    counts_as_loss: bool

    audit_trail: list[str] = field(default_factory=list)

    def validate(self) -> list[str]:
        """Return a list of validation errors. Empty list = valid."""
        errors: list[str] = []

        if not self.plan_id:
            errors.append("plan_id must not be empty")
        if not self.symbol:
            errors.append("symbol must not be empty")
        if not self.timeframe:
            errors.append("timeframe must not be empty")
        if not self.replay_date:
            errors.append("replay_date must not be empty")
        if self.entry_candle_index < 0:
            errors.append(
                f"entry_candle_index must be >= 0, got {self.entry_candle_index}"
            )
        if self.entry_timestamp <= 0:
            errors.append(f"entry_timestamp must be > 0, got {self.entry_timestamp}")
        if (
            self.exit_candle_index is not None
            and self.exit_candle_index < self.entry_candle_index
        ):
            errors.append(
                "exit_candle_index cannot be before entry_candle_index; "
                f"got exit={self.exit_candle_index}, entry={self.entry_candle_index}"
            )
        if self.exit_timestamp is not None and self.exit_timestamp <= 0:
            errors.append(f"exit_timestamp must be > 0, got {self.exit_timestamp}")
        if self.outcome_status not in ExecutionOutcome.ALL_VALUES:
            errors.append(
                f"outcome_status {self.outcome_status!r} not in "
                f"{sorted(ExecutionOutcome.ALL_VALUES)}"
            )
        if self.counts_as_win and self.counts_as_loss:
            errors.append("result cannot count as both win and loss")
        if not self.exit_reason:
            errors.append("exit_reason must not be empty")
        if not self.audit_trail:
            errors.append("audit_trail must be non-empty")

        if self.outcome_status == ExecutionOutcome.AMBIGUOUS_BOTH_TOUCHED:
            if self.realized_r is not None:
                errors.append("AMBIGUOUS_BOTH_TOUCHED must have realized_r=None")
            if self.counts_as_win or self.counts_as_loss:
                errors.append("AMBIGUOUS_BOTH_TOUCHED cannot count as win or loss")

        if self.outcome_status == ExecutionOutcome.UNRESOLVED_END_OF_REPLAY:
            if self.realized_r is not None:
                errors.append("UNRESOLVED_END_OF_REPLAY must have realized_r=None")
            if self.counts_as_win or self.counts_as_loss:
                errors.append("UNRESOLVED_END_OF_REPLAY cannot count as win or loss")

        if self.outcome_status == ExecutionOutcome.SKIPPED_REJECTED_PLAN:
            if self.exit_candle_index is not None:
                errors.append("SKIPPED_REJECTED_PLAN must have exit_candle_index=None")
            if self.exit_timestamp is not None:
                errors.append("SKIPPED_REJECTED_PLAN must have exit_timestamp=None")
            if self.exit_price is not None:
                errors.append("SKIPPED_REJECTED_PLAN must have exit_price=None")
            if self.realized_r is not None:
                errors.append("SKIPPED_REJECTED_PLAN must have realized_r=None")

        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "replay_date": self.replay_date,
            "entry_candle_index": self.entry_candle_index,
            "entry_timestamp": self.entry_timestamp,
            "exit_candle_index": self.exit_candle_index,
            "exit_timestamp": self.exit_timestamp,
            "exit_price": self.exit_price,
            "exit_reason": self.exit_reason,
            "realized_r": self.realized_r,
            "outcome_status": self.outcome_status,
            "counts_as_win": self.counts_as_win,
            "counts_as_loss": self.counts_as_loss,
            "audit_trail": list(self.audit_trail),
        }

    def to_jsonl_line(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "OutcomeResult":
        return cls(
            plan_id=str(d["plan_id"]),
            symbol=str(d["symbol"]),
            timeframe=str(d["timeframe"]),
            replay_date=str(d["replay_date"]),
            entry_candle_index=int(d["entry_candle_index"]),
            entry_timestamp=int(d["entry_timestamp"]),
            exit_candle_index=(
                int(d["exit_candle_index"])
                if d.get("exit_candle_index") is not None
                else None
            ),
            exit_timestamp=(
                int(d["exit_timestamp"])
                if d.get("exit_timestamp") is not None
                else None
            ),
            exit_price=(
                float(d["exit_price"])
                if d.get("exit_price") is not None
                else None
            ),
            exit_reason=str(d["exit_reason"]),
            realized_r=(
                float(d["realized_r"])
                if d.get("realized_r") is not None
                else None
            ),
            outcome_status=str(d["outcome_status"]),
            counts_as_win=bool(d["counts_as_win"]),
            counts_as_loss=bool(d["counts_as_loss"]),
            audit_trail=list(d.get("audit_trail", [])),
        )
