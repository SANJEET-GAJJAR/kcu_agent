"""Phase 7D deterministic human-friendly review exports."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.review.decision import _load_review_queue, load_human_review_decisions
from src.review.queue import HumanReviewQueueError
from src.review.revision import (
    HumanReviewDecisionState,
    load_human_review_revisions,
    resolve_human_review_decision_state,
)
from src.statistics.reporting import _load_json_object


class ReviewExportStatus:
    """Current human-review state for one review item."""

    UNREVIEWED = "UNREVIEWED"
    REVIEWED = "REVIEWED"
    REVISED = "REVISED"
    NEEDS_MORE_INFO = "NEEDS_MORE_INFO"


@dataclass(frozen=True)
class HumanReviewExportArtifacts:
    """Filesystem outputs produced by Phase 7D review export."""

    run_dir: Path
    review_dashboard_md_path: Path
    review_dashboard_json_path: Path
    review_items_md_path: Path
    review_items_json_path: Path


@dataclass
class HumanReviewExportResult:
    """In-memory review export payloads plus filesystem artifact paths."""

    dashboard_payload: dict[str, Any]
    items_payload: dict[str, Any]
    artifacts: HumanReviewExportArtifacts


def build_human_review_export(run_dir: Path | str) -> HumanReviewExportResult:
    """Build deterministic review dashboard and item exports."""
    run_dir = Path(run_dir)
    daily_report = _load_json_object(
        run_dir / "daily_report.json",
        description="daily report",
    )
    if daily_report.get("report_status") != "valid":
        raise HumanReviewQueueError(
            f"Human review export requires daily report_status='valid', got {daily_report.get('report_status')!r}"
        )
    metadata = daily_report.get("metadata")
    if not isinstance(metadata, dict):
        raise HumanReviewQueueError("Daily report metadata must be a JSON object")

    queue_path = _resolve_review_queue_path(run_dir)
    queue_entries = sorted(
        _load_review_queue(queue_path),
        key=lambda entry: (entry.entry_timestamp, entry.entry_candle_index, entry.review_id),
    )
    decisions = load_human_review_decisions(run_dir / "human_review_decisions.jsonl")
    decision_review_ids = {decision.review_id for decision in decisions}
    if len(decision_review_ids) != len(decisions):
        raise HumanReviewQueueError("Duplicate original decisions remain invalid")
    revisions = load_human_review_revisions(run_dir / "human_review_revisions.jsonl")

    items: list[dict[str, Any]] = []
    for entry in queue_entries:
        state = _maybe_resolve_state(run_dir, entry.review_id, decisions=decisions, revisions=revisions)
        (
            current_review_status,
            latest_effective_label,
            notes,
            revision_count,
            outcome_id,
            human_setup_label,
            policy_exclusion_reason,
        ) = _state_fields(
            entry,
            state,
        )
        items.append(
            {
                "review_queue_id": entry.review_id,
                "trade_plan_id": entry.plan_id,
                "outcome_id": outcome_id,
                "setup_type": entry.setup_type,
                "direction": entry.direction,
                "grade": entry.grade,
                "outcome_status": entry.outcome_status,
                "realized_r": entry.realized_r,
                "current_review_status": current_review_status,
                "latest_effective_label": latest_effective_label,
                "revision_count": revision_count,
                "notes": notes,
                "human_setup_label": human_setup_label,
                "policy_exclusion_reason": policy_exclusion_reason,
                "entry_timestamp": entry.entry_timestamp,
            }
        )

    dashboard_payload = _build_dashboard_payload(metadata, items, daily_report)
    items_payload = {
        "run_id": metadata.get("run_id"),
        "ticker": metadata.get("ticker"),
        "date": metadata.get("date"),
        "items": items,
    }

    artifacts = HumanReviewExportArtifacts(
        run_dir=run_dir,
        review_dashboard_md_path=run_dir / "review_dashboard.md",
        review_dashboard_json_path=run_dir / "review_dashboard.json",
        review_items_md_path=run_dir / "review_items.md",
        review_items_json_path=run_dir / "review_items.json",
    )

    _write_json(artifacts.review_dashboard_json_path, dashboard_payload)
    _write_json(artifacts.review_items_json_path, items_payload)
    artifacts.review_dashboard_md_path.write_text(
        _render_dashboard_markdown(dashboard_payload),
        encoding="utf-8",
    )
    artifacts.review_items_md_path.write_text(
        _render_items_markdown(items_payload),
        encoding="utf-8",
    )

    return HumanReviewExportResult(
        dashboard_payload=dashboard_payload,
        items_payload=items_payload,
        artifacts=artifacts,
    )


def _resolve_review_queue_path(run_dir: Path) -> Path:
    preferred = run_dir / "human_review_queue.jsonl"
    alias = run_dir / "review_queue.jsonl"
    if preferred.exists():
        return preferred
    if alias.exists():
        return alias
    raise HumanReviewQueueError(
        f"Required JSONL file not found: {preferred}"
    )


def _maybe_resolve_state(
    run_dir: Path,
    review_id: str,
    *,
    decisions,
    revisions,
) -> HumanReviewDecisionState | None:
    if not any(decision.review_id == review_id for decision in decisions):
        return None
    return resolve_human_review_decision_state(
        run_dir,
        review_id,
        decisions=decisions,
        revisions=revisions,
    )


def _state_fields(
    entry,
    state: HumanReviewDecisionState | None,
) -> tuple[str, str | None, str | None, int, str, str | None, str | None]:
    if state is None:
        return (
            ReviewExportStatus.UNREVIEWED,
            None,
            None,
            0,
            entry.plan_id,
            None,
            None,
        )

    latest = state.effective_decision
    revision_count = len(state.revisions)
    if latest.label == "NEEDS_MORE_INFO":
        status = ReviewExportStatus.NEEDS_MORE_INFO
    elif revision_count > 0:
        status = ReviewExportStatus.REVISED
    else:
        status = ReviewExportStatus.REVIEWED
    return (
        status,
        latest.label,
        latest.notes,
        revision_count,
        state.original_decision.outcome_id,
        latest.human_setup_label,
        latest.policy_exclusion_reason,
    )


def _build_dashboard_payload(
    metadata: dict[str, Any],
    items: list[dict[str, Any]],
    daily_report: dict[str, Any],
) -> dict[str, Any]:
    return {
        "run_id": metadata.get("run_id"),
        "ticker": metadata.get("ticker"),
        "date": metadata.get("date"),
        "integrity_status": metadata.get("integrity_status"),
        "source_report_path": metadata.get("source_stats_path"),
        "total_items": len(items),
        "unreviewed_items": [item for item in items if item["current_review_status"] == ReviewExportStatus.UNREVIEWED],
        "reviewed_items": [item for item in items if item["current_review_status"] == ReviewExportStatus.REVIEWED],
        "revised_items": [item for item in items if item["current_review_status"] == ReviewExportStatus.REVISED],
        "needs_more_info_items": [item for item in items if item["current_review_status"] == ReviewExportStatus.NEEDS_MORE_INFO],
        "daily_report_summary": daily_report.get("summary"),
    }


def _render_dashboard_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Review Dashboard",
        "",
        f"- Run ID: `{payload.get('run_id') or 'unknown'}`",
        f"- Ticker: `{payload.get('ticker') or 'unknown'}`",
        f"- Date: `{payload.get('date') or 'unknown'}`",
        f"- Integrity Status: `{payload.get('integrity_status') or 'unknown'}`",
        f"- Total Review Items: {payload['total_items']}",
        "",
    ]
    lines.extend(_render_section("Unreviewed Items", payload["unreviewed_items"]))
    lines.extend([""])
    lines.extend(_render_section("Reviewed Items", payload["reviewed_items"]))
    lines.extend([""])
    lines.extend(_render_section("Revised Items", payload["revised_items"]))
    lines.extend([""])
    lines.extend(_render_section("Needs More Info Items", payload["needs_more_info_items"]))
    lines.append("")
    return "\n".join(lines)


def _render_items_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Review Items",
        "",
        f"- Run ID: `{payload.get('run_id') or 'unknown'}`",
        "",
    ]
    items = payload["items"]
    if not items:
        lines.append("No review items.")
        lines.append("")
        return "\n".join(lines)
    for item in items:
        lines.extend(
            [
                f"## {item['review_queue_id']}",
                "",
                f"- Trade Plan ID: `{item['trade_plan_id']}`",
                f"- Outcome ID: `{item['outcome_id']}`",
                f"- Setup Type: `{item['setup_type']}`",
                f"- Direction: `{item['direction']}`",
                f"- Grade: `{item['grade']}`",
                f"- Outcome Status: `{item['outcome_status']}`",
                f"- Realized R: {_format_scalar(item['realized_r'])}",
                f"- Current Review Status: `{item['current_review_status']}`",
                f"- Latest Effective Label: `{item['latest_effective_label']}`" if item["latest_effective_label"] is not None else "- Latest Effective Label: `n/a`",
                f"- Revision Count: {item['revision_count']}",
                f"- Human Setup Label: `{item['human_setup_label']}`" if item["human_setup_label"] else "- Human Setup Label: `n/a`",
                f"- Policy Exclusion Reason: {item['policy_exclusion_reason']}" if item["policy_exclusion_reason"] else "- Policy Exclusion Reason: n/a",
                f"- Notes: {item['notes']}" if item["notes"] else "- Notes: n/a",
                "",
            ]
        )
    return "\n".join(lines)


def _render_section(title: str, items: list[dict[str, Any]]) -> list[str]:
    lines = [f"## {title}", ""]
    if not items:
        lines.append("No items.")
        return lines
    for item in items:
        lines.append(
            f"- {item['review_queue_id']}: label={_format_scalar(item['latest_effective_label'])}, "
            f"status={item['current_review_status']}, outcome={item['outcome_status']}, "
            f"realized_r={_format_scalar(item['realized_r'])}"
        )
    return lines


def _format_scalar(value: Any) -> str:
    if value is None:
        return "n/a"
    return str(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
