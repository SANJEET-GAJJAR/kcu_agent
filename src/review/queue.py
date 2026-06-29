"""Phase 7A deterministic human review queue builder."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.review.schema import ReviewQueueEntry, ReviewQueueStatus
from src.simulator.outcome import OutcomeResult
from src.simulator.trade_plan import TradePlan
from src.statistics.reporting import (
    DEFAULT_GENERATED_AT,
    _build_canonical_daily_dir,
    _load_json_object,
    _write_optional_copy,
    _write_optional_text,
)


class HumanReviewQueueError(Exception):
    """Raised when review queue inputs are missing or inconsistent."""


@dataclass(frozen=True)
class HumanReviewArtifacts:
    """Filesystem outputs produced by the Phase 7A daily review queue."""

    run_dir: Path
    review_queue_path: Path
    review_summary_path: Path
    canonical_review_queue_path: Path | None
    canonical_review_summary_path: Path | None


@dataclass
class HumanReviewQueueResult:
    """In-memory review queue entries plus filesystem artifact paths."""

    entries: list[ReviewQueueEntry]
    summary: dict[str, Any]
    artifacts: HumanReviewArtifacts


def build_daily_review_queue(
    run_dir: Path | str,
    *,
    report_root: Path | str | None = None,
    ticker: str | None = None,
    trade_date: str | None = None,
    generated_at: str | None = None,
) -> HumanReviewQueueResult:
    """Build deterministic human review queue entries from valid day artifacts."""
    run_dir = Path(run_dir)
    report_payload = _load_json_object(
        run_dir / "daily_report.json",
        description="daily report",
    )
    report_status = report_payload.get("report_status")
    if report_status != "valid":
        raise HumanReviewQueueError(
            f"Daily review queue requires report_status='valid', got {report_status!r}"
        )
    metadata = report_payload.get("metadata")
    if not isinstance(metadata, dict):
        raise HumanReviewQueueError("Daily report metadata must be a JSON object")
    integrity_status = metadata.get("integrity_status")
    if integrity_status != "VALID":
        raise HumanReviewQueueError(
            f"Daily review queue requires integrity_status='VALID', got {integrity_status!r}"
        )

    run_id = _required_string(metadata, "run_id")
    resolved_ticker = ticker or _required_string(metadata, "ticker")
    resolved_date = trade_date or _required_string(metadata, "date")
    canonical_dir = _build_canonical_daily_dir(
        report_root,
        ticker=resolved_ticker,
        trade_date=resolved_date,
        run_id=run_id,
    )
    artifacts = HumanReviewArtifacts(
        run_dir=run_dir,
        review_queue_path=run_dir / "human_review_queue.jsonl",
        review_summary_path=run_dir / "human_review_summary.json",
        canonical_review_queue_path=(
            canonical_dir / "human_review_queue.jsonl" if canonical_dir is not None else None
        ),
        canonical_review_summary_path=(
            canonical_dir / "human_review_summary.json" if canonical_dir is not None else None
        ),
    )

    valid_plans = _load_trade_plans(run_dir / "trade_plans.jsonl")
    outcomes = _load_outcomes(run_dir / "trade_outcomes.jsonl")

    plan_by_id = {plan.plan_id: plan for plan in valid_plans}
    ordered_outcomes = sorted(
        outcomes,
        key=lambda o: (
            o.entry_candle_index,
            o.exit_candle_index if o.exit_candle_index is not None else 10**9,
            o.plan_id,
        ),
    )
    entries: list[ReviewQueueEntry] = []
    for outcome in ordered_outcomes:
        plan = plan_by_id.get(outcome.plan_id)
        if plan is None:
            raise HumanReviewQueueError(
                f"Outcome {outcome.plan_id!r} has no matching valid trade plan"
            )
        entry = ReviewQueueEntry(
            review_id=f"{run_id}:{plan.plan_id}",
            queue_status=ReviewQueueStatus.PENDING,
            created_at=generated_at or DEFAULT_GENERATED_AT,
            run_id=run_id,
            plan_id=plan.plan_id,
            symbol=plan.symbol,
            timeframe=plan.timeframe,
            replay_date=plan.replay_date,
            setup_type=plan.setup_type,
            watch_type=plan.watch_type,
            grade=plan.grade,
            direction=plan.direction,
            plan_status=plan.plan_status,
            source_candle_index=plan.source_candle_index,
            entry_candle_index=outcome.entry_candle_index,
            entry_timestamp=outcome.entry_timestamp,
            outcome_status=outcome.outcome_status,
            exit_reason=outcome.exit_reason,
            realized_r=outcome.realized_r,
            counts_as_win=outcome.counts_as_win,
            counts_as_loss=outcome.counts_as_loss,
            integrity_status=integrity_status,
            evidence_paths={
                "daily_report_json": str((run_dir / "daily_report.json").resolve()),
                "daily_report_md": str((run_dir / "daily_report.md").resolve()),
                "trade_plans_jsonl": str((run_dir / "trade_plans.jsonl").resolve()),
                "trade_outcomes_jsonl": str((run_dir / "trade_outcomes.jsonl").resolve()),
                "stats_summary_json": str((run_dir / "stats_summary.json").resolve()),
            },
        )
        errors = entry.validate()
        if errors:
            raise HumanReviewQueueError(
                f"Invalid review queue entry for plan_id={plan.plan_id}: {'; '.join(errors)}"
            )
        entries.append(entry)

    _write_jsonl_entries(artifacts.review_queue_path, entries)
    canonical_queue_lines = "".join(entry.to_jsonl_line() + "\n" for entry in entries)
    _write_optional_text(artifacts.canonical_review_queue_path, canonical_queue_lines)

    summary = {
        "run_id": run_id,
        "ticker": resolved_ticker,
        "date": resolved_date,
        "integrity_status": integrity_status,
        "review_entry_count": len(entries),
        "pending_review_count": len(entries),
        "review_ids": [entry.review_id for entry in entries],
        "source_report_path": str((run_dir / "daily_report.json").resolve()),
    }
    _write_json(artifacts.review_summary_path, summary)
    _write_optional_copy(artifacts.canonical_review_summary_path, summary)

    return HumanReviewQueueResult(
        entries=entries,
        summary=summary,
        artifacts=artifacts,
    )


def _load_trade_plans(path: Path) -> list[TradePlan]:
    return [
        _parse_trade_plan(path, lineno, row)
        for lineno, row in _read_jsonl_lines(path)
    ]


def _load_outcomes(path: Path) -> list[OutcomeResult]:
    return [
        _parse_outcome(path, lineno, row)
        for lineno, row in _read_jsonl_lines(path)
    ]


def _read_jsonl_lines(path: Path) -> list[tuple[int, dict[str, Any]]]:
    if not path.exists():
        raise HumanReviewQueueError(f"Required JSONL file not found: {path}")
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


def _parse_trade_plan(path: Path, lineno: int, row: dict[str, Any]) -> TradePlan:
    try:
        plan = TradePlan.from_dict(row)
    except (KeyError, TypeError, ValueError) as exc:
        raise HumanReviewQueueError(
            f"Malformed trade plan record at {path}:{lineno}: {exc}"
        ) from exc
    errors = plan.validate()
    if errors:
        raise HumanReviewQueueError(
            f"Invalid trade plan record at {path}:{lineno}: {'; '.join(errors)}"
        )
    return plan


def _parse_outcome(path: Path, lineno: int, row: dict[str, Any]) -> OutcomeResult:
    try:
        outcome = OutcomeResult.from_dict(row)
    except (KeyError, TypeError, ValueError) as exc:
        raise HumanReviewQueueError(
            f"Malformed trade outcome record at {path}:{lineno}: {exc}"
        ) from exc
    errors = outcome.validate()
    if errors:
        raise HumanReviewQueueError(
            f"Invalid trade outcome record at {path}:{lineno}: {'; '.join(errors)}"
        )
    return outcome


def _required_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise HumanReviewQueueError(
            f"Daily report metadata must include non-empty {key!r}, got {value!r}"
        )
    return value


def _write_jsonl_entries(path: Path, entries: list[ReviewQueueEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(entry.to_jsonl_line() + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
