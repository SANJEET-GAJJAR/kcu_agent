"""Phase 7C deterministic human review revision records."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.review.decision import (
    HumanReviewDecision,
    ReviewDecisionLabel,
    load_human_review_decisions,
)
from src.review.queue import HumanReviewQueueError


@dataclass
class HumanReviewRevision:
    """One append-only revision against an existing human review decision."""

    revision_id: str
    original_decision_id: str
    review_id: str
    revised_label: str
    reviewer: str
    timestamp: str
    revision_reason: str
    notes: str | None = None
    revision_sequence: int | None = None
    previous_effective_decision_id: str | None = None

    def validate(self) -> list[str]:
        """Return validation errors. Empty list means valid."""
        errors: list[str] = []
        if not self.revision_id:
            errors.append("revision_id must not be empty")
        if not self.original_decision_id:
            errors.append("original_decision_id must not be empty")
        if not self.review_id:
            errors.append("review_id must not be empty")
        if self.revised_label not in ReviewDecisionLabel.ALL_VALUES:
            errors.append(
                f"revised_label {self.revised_label!r} not in {sorted(ReviewDecisionLabel.ALL_VALUES)}"
            )
        if not self.reviewer:
            errors.append("reviewer must not be empty")
        if not self.timestamp:
            errors.append("timestamp must not be empty")
        if not self.revision_reason:
            errors.append("revision_reason must not be empty")
        if self.notes is not None and not isinstance(self.notes, str):
            errors.append("notes must be a string when present")
        if self.revision_sequence is not None and self.revision_sequence <= 0:
            errors.append("revision_sequence must be > 0 when present")
        if self.revision_sequence is None and self.previous_effective_decision_id is None:
            errors.append(
                "revision must include previous_effective_decision_id or revision_sequence"
            )
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "revision_id": self.revision_id,
            "original_decision_id": self.original_decision_id,
            "review_id": self.review_id,
            "revised_label": self.revised_label,
            "reviewer": self.reviewer,
            "timestamp": self.timestamp,
            "revision_reason": self.revision_reason,
            "notes": self.notes,
            "revision_sequence": self.revision_sequence,
            "previous_effective_decision_id": self.previous_effective_decision_id,
        }

    def to_jsonl_line(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "HumanReviewRevision":
        return cls(
            revision_id=str(d["revision_id"]),
            original_decision_id=str(d["original_decision_id"]),
            review_id=str(d["review_id"]),
            revised_label=str(d["revised_label"]),
            reviewer=str(d["reviewer"]),
            timestamp=str(d["timestamp"]),
            revision_reason=str(d["revision_reason"]),
            notes=d.get("notes"),
            revision_sequence=(
                int(d["revision_sequence"])
                if d.get("revision_sequence") is not None
                else None
            ),
            previous_effective_decision_id=d.get("previous_effective_decision_id"),
        )


@dataclass(frozen=True)
class EffectiveReviewDecision:
    """Resolved effective decision after applying zero or more revisions."""

    decision_id: str
    review_id: str
    label: str
    reviewer: str
    timestamp: str
    notes: str | None
    human_setup_label: str | None
    policy_exclusion_reason: str | None
    source_type: str
    revision_reason: str | None
    revision_sequence: int | None


@dataclass
class HumanReviewDecisionState:
    """Original decision plus revision history and effective latest decision."""

    original_decision: HumanReviewDecision
    revisions: list[HumanReviewRevision]
    effective_decision: EffectiveReviewDecision
    revision_history: list[EffectiveReviewDecision]


def load_human_review_revisions(path: Path | str) -> list[HumanReviewRevision]:
    """Load deterministic human review revisions from JSONL."""
    path = Path(path)
    if not path.exists():
        return []
    revisions: list[HumanReviewRevision] = []
    for lineno, row in _read_jsonl_lines(path):
        try:
            revision = HumanReviewRevision.from_dict(row)
        except (KeyError, TypeError, ValueError) as exc:
            raise HumanReviewQueueError(
                f"Malformed human review revision at {path}:{lineno}: {exc}"
            ) from exc
        errors = revision.validate()
        if errors:
            raise HumanReviewQueueError(
                f"Invalid human review revision at {path}:{lineno}: {'; '.join(errors)}"
            )
        revisions.append(revision)
    return revisions


def append_human_review_revision(
    run_dir: Path | str,
    revision: HumanReviewRevision,
) -> Path:
    """Append one validated human review revision to the revision log."""
    run_dir = Path(run_dir)
    errors = revision.validate()
    if errors:
        raise HumanReviewQueueError(
            "Invalid human review revision: " + "; ".join(errors)
        )

    decisions = load_human_review_decisions(run_dir / "human_review_decisions.jsonl")
    decision_by_id = {decision.decision_id: decision for decision in decisions}
    original = decision_by_id.get(revision.original_decision_id)
    if original is None:
        raise HumanReviewQueueError(
            f"Missing original decision reference for original_decision_id={revision.original_decision_id!r}"
        )
    if revision.review_id != original.review_id:
        raise HumanReviewQueueError(
            f"review_id mismatch for original_decision_id={revision.original_decision_id!r}: "
            f"revision={revision.review_id!r} decision={original.review_id!r}"
        )

    existing = load_human_review_revisions(run_dir / "human_review_revisions.jsonl")
    if any(item.revision_id == revision.revision_id for item in existing):
        raise HumanReviewQueueError(
            f"Duplicate revision_id {revision.revision_id!r}"
        )

    state = resolve_human_review_decision_state(
        run_dir,
        revision.review_id,
        decisions=decisions,
        revisions=existing,
    )
    current_effective = state.effective_decision.decision_id

    if revision.previous_effective_decision_id is not None:
        if revision.previous_effective_decision_id != current_effective:
            raise HumanReviewQueueError(
                f"previous_effective_decision_id must reference current effective decision "
                f"{current_effective!r}, got {revision.previous_effective_decision_id!r}"
            )
    if revision.revision_sequence is not None:
        next_sequence = len(existing) + 1
        if revision.revision_sequence != next_sequence:
            raise HumanReviewQueueError(
                f"revision_sequence must be monotonic and equal to next sequence "
                f"{next_sequence}, got {revision.revision_sequence}"
            )
    elif revision.previous_effective_decision_id is None:
        raise HumanReviewQueueError(
            "revision must include previous_effective_decision_id or revision_sequence"
        )

    path = run_dir / "human_review_revisions.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(revision.to_jsonl_line() + "\n")
    return path


def resolve_human_review_decision_state(
    run_dir: Path | str,
    review_id: str,
    *,
    decisions: list[HumanReviewDecision] | None = None,
    revisions: list[HumanReviewRevision] | None = None,
) -> HumanReviewDecisionState:
    """Resolve original decision, revisions, and effective latest decision."""
    run_dir = Path(run_dir)
    decisions = decisions if decisions is not None else load_human_review_decisions(
        run_dir / "human_review_decisions.jsonl"
    )
    revisions = revisions if revisions is not None else load_human_review_revisions(
        run_dir / "human_review_revisions.jsonl"
    )

    matching_decisions = [decision for decision in decisions if decision.review_id == review_id]
    if not matching_decisions:
        raise HumanReviewQueueError(
            f"No human review decision found for review_id={review_id!r}"
        )
    if len(matching_decisions) > 1:
        raise HumanReviewQueueError(
            f"Duplicate original decisions remain invalid for review_id={review_id!r}"
        )

    original = matching_decisions[0]
    matching_revisions = [
        revision
        for revision in revisions
        if revision.review_id == review_id
    ]
    ordered_revisions = sorted(
        matching_revisions,
        key=lambda item: (
            item.revision_sequence if item.revision_sequence is not None else 10**9,
            item.timestamp,
            item.revision_id,
        ),
    )

    history: list[EffectiveReviewDecision] = [
        EffectiveReviewDecision(
            decision_id=original.decision_id,
            review_id=original.review_id,
            label=original.label,
            reviewer=original.reviewer,
            timestamp=original.timestamp,
            notes=original.notes,
            human_setup_label=original.human_setup_label,
            policy_exclusion_reason=original.policy_exclusion_reason,
            source_type="original_decision",
            revision_reason=None,
            revision_sequence=None,
        )
    ]
    current_effective_id = original.decision_id
    previous_sequence = 0
    for revision in ordered_revisions:
        if revision.original_decision_id != original.decision_id:
            raise HumanReviewQueueError(
                f"Revision {revision.revision_id!r} references a different original decision"
            )
        if (
            revision.previous_effective_decision_id is not None
            and revision.previous_effective_decision_id != current_effective_id
        ):
            raise HumanReviewQueueError(
                f"Revision {revision.revision_id!r} does not reference previous effective decision "
                f"{current_effective_id!r}"
            )
        if revision.revision_sequence is not None:
            if revision.revision_sequence != previous_sequence + 1:
                raise HumanReviewQueueError(
                    f"Revision {revision.revision_id!r} has non-monotonic revision_sequence "
                    f"{revision.revision_sequence}"
                )
            previous_sequence = revision.revision_sequence

        effective = EffectiveReviewDecision(
            decision_id=revision.revision_id,
            review_id=revision.review_id,
            label=revision.revised_label,
            reviewer=revision.reviewer,
            timestamp=revision.timestamp,
            notes=revision.notes,
            human_setup_label=history[-1].human_setup_label,
            policy_exclusion_reason=history[-1].policy_exclusion_reason,
            source_type="revision",
            revision_reason=revision.revision_reason,
            revision_sequence=revision.revision_sequence,
        )
        history.append(effective)
        current_effective_id = revision.revision_id

    return HumanReviewDecisionState(
        original_decision=original,
        revisions=ordered_revisions,
        effective_decision=history[-1],
        revision_history=history,
    )


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
