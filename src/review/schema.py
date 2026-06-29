"""Phase 7A deterministic schema for human review queue entries."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


class ReviewQueueStatus:
    """Allowed queue states for Phase 7A review entries."""

    PENDING = "PENDING"
    ALL_VALUES: frozenset[str] = frozenset({PENDING})


@dataclass
class ReviewQueueEntry:
    """One deterministic human-review queue entry for a completed trade."""

    review_id: str
    queue_status: str
    created_at: str

    run_id: str
    plan_id: str
    symbol: str
    timeframe: str
    replay_date: str

    setup_type: str
    watch_type: str
    grade: str | None
    direction: str
    plan_status: str
    source_candle_index: int
    entry_candle_index: int
    entry_timestamp: int

    outcome_status: str
    exit_reason: str
    realized_r: float | None
    counts_as_win: bool
    counts_as_loss: bool

    integrity_status: str
    evidence_paths: dict[str, str] = field(default_factory=dict)

    def validate(self) -> list[str]:
        """Return validation errors. Empty list means valid."""
        errors: list[str] = []
        if not self.review_id:
            errors.append("review_id must not be empty")
        if self.queue_status not in ReviewQueueStatus.ALL_VALUES:
            errors.append(
                f"queue_status {self.queue_status!r} not in "
                f"{sorted(ReviewQueueStatus.ALL_VALUES)}"
            )
        if not self.created_at:
            errors.append("created_at must not be empty")
        if not self.run_id:
            errors.append("run_id must not be empty")
        if not self.plan_id:
            errors.append("plan_id must not be empty")
        if not self.symbol:
            errors.append("symbol must not be empty")
        if not self.timeframe:
            errors.append("timeframe must not be empty")
        if not self.replay_date:
            errors.append("replay_date must not be empty")
        if not self.setup_type:
            errors.append("setup_type must not be empty")
        if not self.watch_type:
            errors.append("watch_type must not be empty")
        if not self.direction:
            errors.append("direction must not be empty")
        if not self.plan_status:
            errors.append("plan_status must not be empty")
        if self.source_candle_index < 0:
            errors.append("source_candle_index must be >= 0")
        if self.entry_candle_index < 0:
            errors.append("entry_candle_index must be >= 0")
        if self.entry_timestamp <= 0:
            errors.append("entry_timestamp must be > 0")
        if not self.outcome_status:
            errors.append("outcome_status must not be empty")
        if not self.exit_reason:
            errors.append("exit_reason must not be empty")
        if self.integrity_status != "VALID":
            errors.append(
                f"integrity_status must be 'VALID' for Phase 7A queue entries, got {self.integrity_status!r}"
            )
        required_paths = {
            "daily_report_json",
            "daily_report_md",
            "trade_plans_jsonl",
            "trade_outcomes_jsonl",
            "stats_summary_json",
        }
        missing_paths = sorted(
            key for key in required_paths
            if key not in self.evidence_paths or not self.evidence_paths[key]
        )
        if missing_paths:
            errors.append(
                f"evidence_paths missing required keys: {missing_paths}"
            )
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "queue_status": self.queue_status,
            "created_at": self.created_at,
            "run_id": self.run_id,
            "plan_id": self.plan_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "replay_date": self.replay_date,
            "setup_type": self.setup_type,
            "watch_type": self.watch_type,
            "grade": self.grade,
            "direction": self.direction,
            "plan_status": self.plan_status,
            "source_candle_index": self.source_candle_index,
            "entry_candle_index": self.entry_candle_index,
            "entry_timestamp": self.entry_timestamp,
            "outcome_status": self.outcome_status,
            "exit_reason": self.exit_reason,
            "realized_r": self.realized_r,
            "counts_as_win": self.counts_as_win,
            "counts_as_loss": self.counts_as_loss,
            "integrity_status": self.integrity_status,
            "evidence_paths": dict(self.evidence_paths),
        }

    def to_jsonl_line(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ReviewQueueEntry":
        return cls(
            review_id=str(d["review_id"]),
            queue_status=str(d["queue_status"]),
            created_at=str(d["created_at"]),
            run_id=str(d["run_id"]),
            plan_id=str(d["plan_id"]),
            symbol=str(d["symbol"]),
            timeframe=str(d["timeframe"]),
            replay_date=str(d["replay_date"]),
            setup_type=str(d["setup_type"]),
            watch_type=str(d["watch_type"]),
            grade=d.get("grade"),
            direction=str(d["direction"]),
            plan_status=str(d["plan_status"]),
            source_candle_index=int(d["source_candle_index"]),
            entry_candle_index=int(d["entry_candle_index"]),
            entry_timestamp=int(d["entry_timestamp"]),
            outcome_status=str(d["outcome_status"]),
            exit_reason=str(d["exit_reason"]),
            realized_r=(
                float(d["realized_r"])
                if d.get("realized_r") is not None
                else None
            ),
            counts_as_win=bool(d["counts_as_win"]),
            counts_as_loss=bool(d["counts_as_loss"]),
            integrity_status=str(d["integrity_status"]),
            evidence_paths={
                str(key): str(value)
                for key, value in dict(d.get("evidence_paths", {})).items()
            },
        )
