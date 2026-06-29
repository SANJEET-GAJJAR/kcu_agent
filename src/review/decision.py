"""Phase 7B deterministic human review decision records."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.review.queue import HumanReviewQueueError, _load_outcomes, _load_trade_plans
from src.review.schema import ReviewQueueEntry


class ReviewDecisionLabel:
    """Allowed deterministic human review decision labels."""

    CORRECT = "CORRECT"
    INCORRECT = "INCORRECT"
    VALID_WIN = "VALID_WIN"
    VALID_LOSS = "VALID_LOSS"
    INVALID_WIN = "INVALID_WIN"
    INVALID_LOSS = "INVALID_LOSS"
    BAD_TRADE = "BAD_TRADE"
    EXCLUDED_PREMARKET = "EXCLUDED_PREMARKET"
    MISSED_SETUP = "MISSED_SETUP"
    WRONG_SETUP_TYPE = "WRONG_SETUP_TYPE"
    WRONG_ENTRY = "WRONG_ENTRY"
    WRONG_STOP = "WRONG_STOP"
    WRONG_CONTEXT = "WRONG_CONTEXT"
    NEEDS_MORE_INFO = "NEEDS_MORE_INFO"
    ALL_VALUES: frozenset[str] = frozenset(
        {
            CORRECT,
            INCORRECT,
            VALID_WIN,
            VALID_LOSS,
            INVALID_WIN,
            INVALID_LOSS,
            BAD_TRADE,
            EXCLUDED_PREMARKET,
            MISSED_SETUP,
            WRONG_SETUP_TYPE,
            WRONG_ENTRY,
            WRONG_STOP,
            WRONG_CONTEXT,
            NEEDS_MORE_INFO,
        }
    )


@dataclass
class HumanReviewDecision:
    """One append-only human decision for a queued review item."""

    decision_id: str
    review_id: str
    plan_id: str
    outcome_id: str
    label: str
    reviewer: str
    timestamp: str
    notes: str | None = None
    human_setup_label: str | None = None
    policy_exclusion_reason: str | None = None

    def validate(self) -> list[str]:
        """Return validation errors. Empty list means valid."""
        errors: list[str] = []
        if not self.decision_id:
            errors.append("decision_id must not be empty")
        if not self.review_id:
            errors.append("review_id must not be empty")
        if not self.plan_id:
            errors.append("plan_id must not be empty")
        if not self.outcome_id:
            errors.append("outcome_id must not be empty")
        if self.label not in ReviewDecisionLabel.ALL_VALUES:
            errors.append(
                f"label {self.label!r} not in {sorted(ReviewDecisionLabel.ALL_VALUES)}"
            )
        if not self.reviewer:
            errors.append("reviewer must not be empty")
        if not self.timestamp:
            errors.append("timestamp must not be empty")
        if self.notes is not None and not isinstance(self.notes, str):
            errors.append("notes must be a string when present")
        if self.human_setup_label is not None and not isinstance(self.human_setup_label, str):
            errors.append("human_setup_label must be a string when present")
        if self.policy_exclusion_reason is not None and not isinstance(
            self.policy_exclusion_reason, str
        ):
            errors.append("policy_exclusion_reason must be a string when present")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "review_id": self.review_id,
            "plan_id": self.plan_id,
            "outcome_id": self.outcome_id,
            "label": self.label,
            "reviewer": self.reviewer,
            "timestamp": self.timestamp,
            "notes": self.notes,
            "human_setup_label": self.human_setup_label,
            "policy_exclusion_reason": self.policy_exclusion_reason,
        }

    def to_jsonl_line(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "HumanReviewDecision":
        return cls(
            decision_id=str(d["decision_id"]),
            review_id=str(d["review_id"]),
            plan_id=str(d["plan_id"]),
            outcome_id=str(d["outcome_id"]),
            label=str(d["label"]),
            reviewer=str(d["reviewer"]),
            timestamp=str(d["timestamp"]),
            notes=d.get("notes"),
            human_setup_label=d.get("human_setup_label"),
            policy_exclusion_reason=d.get("policy_exclusion_reason"),
        )


def load_human_review_decisions(path: Path | str) -> list[HumanReviewDecision]:
    """Load deterministic human review decisions from JSONL."""
    path = Path(path)
    if not path.exists():
        return []
    decisions: list[HumanReviewDecision] = []
    for lineno, row in _read_jsonl_lines(path):
        try:
            decision = HumanReviewDecision.from_dict(row)
        except (KeyError, TypeError, ValueError) as exc:
            raise HumanReviewQueueError(
                f"Malformed human review decision at {path}:{lineno}: {exc}"
            ) from exc
        errors = decision.validate()
        if errors:
            raise HumanReviewQueueError(
                f"Invalid human review decision at {path}:{lineno}: {'; '.join(errors)}"
            )
        decisions.append(decision)
    return decisions


def append_human_review_decision(
    run_dir: Path | str,
    decision: HumanReviewDecision,
) -> Path:
    """Append one validated human review decision to the day-run decision log."""
    run_dir = Path(run_dir)
    errors = decision.validate()
    if errors:
        raise HumanReviewQueueError(
            "Invalid human review decision: " + "; ".join(errors)
        )

    queue_entries = _load_review_queue(run_dir / "human_review_queue.jsonl")
    queue_by_review_id = {entry.review_id: entry for entry in queue_entries}
    queue_entry = queue_by_review_id.get(decision.review_id)
    if queue_entry is None:
        raise HumanReviewQueueError(
            f"Missing queue item reference for review_id={decision.review_id!r}"
        )
    if decision.plan_id != queue_entry.plan_id:
        raise HumanReviewQueueError(
            f"plan_id mismatch for review_id={decision.review_id!r}: "
            f"decision={decision.plan_id!r} queue={queue_entry.plan_id!r}"
        )

    valid_plans = {plan.plan_id for plan in _load_trade_plans(run_dir / "trade_plans.jsonl")}
    if decision.plan_id not in valid_plans:
        raise HumanReviewQueueError(
            f"Missing trade plan reference for plan_id={decision.plan_id!r}"
        )

    outcome_ids = {outcome.plan_id for outcome in _load_outcomes(run_dir / "trade_outcomes.jsonl")}
    if decision.outcome_id not in outcome_ids:
        raise HumanReviewQueueError(
            f"Missing outcome reference for outcome_id={decision.outcome_id!r}"
        )

    path = run_dir / "human_review_decisions.jsonl"
    existing = load_human_review_decisions(path)
    if any(item.review_id == decision.review_id for item in existing):
        raise HumanReviewQueueError(
            f"Duplicate decision for review_id={decision.review_id!r}"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(decision.to_jsonl_line() + "\n")
    return path


def _load_review_queue(path: Path) -> list[ReviewQueueEntry]:
    if not path.exists():
        raise HumanReviewQueueError(f"Required JSONL file not found: {path}")
    entries: list[ReviewQueueEntry] = []
    for lineno, row in _read_jsonl_lines(path):
        try:
            entry = ReviewQueueEntry.from_dict(row)
        except (KeyError, TypeError, ValueError) as exc:
            raise HumanReviewQueueError(
                f"Malformed review queue record at {path}:{lineno}: {exc}"
            ) from exc
        errors = entry.validate()
        if errors:
            raise HumanReviewQueueError(
                f"Invalid review queue record at {path}:{lineno}: {'; '.join(errors)}"
            )
        entries.append(entry)
    return entries


def _read_jsonl_lines(path: Path) -> list[tuple[int, dict[str, Any]]]:
    rows: list[tuple[int, dict[str, Any]]] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise HumanReviewQueueError(
                f"Malformed JSONL record at {path}:{lineno}: {exc}"
            ) from exc
        if not isinstance(parsed, dict):
            raise HumanReviewQueueError(
                f"JSONL record at {path}:{lineno} must be an object"
            )
        rows.append((lineno, parsed))
    return rows
