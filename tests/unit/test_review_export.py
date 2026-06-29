"""Unit tests for Phase 7D human-friendly review export."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.review import (
    HumanReviewDecision,
    HumanReviewQueueError,
    HumanReviewRevision,
    ReviewDecisionLabel,
    ReviewExportStatus,
    append_human_review_decision,
    append_human_review_revision,
    build_daily_review_queue,
    build_human_review_export,
)
from src.statistics import build_daily_report, build_statistics


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, separators=(",", ":")) + "\n")


def _write_run_dir(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(
        run_dir / "trade_plans.jsonl",
        [
            {
                "run_id": "run-001",
                "record_type": "trade_plan",
                "plan_id": "p1",
                "timestamp": 1705334400,
                "symbol": "TSLA",
                "timeframe": "2",
                "replay_date": "2024-01-15",
                "candle_index": 1,
                "setup_type": "FAILED_LTP",
                "watch_type": "FAILED_LTP_WATCH",
                "grade": "A",
                "source_candle_index": 0,
                "direction": "long",
                "entry_trigger": 100.0,
                "stop": 98.0,
                "risk": 2.0,
                "target_1_5r": 103.0,
                "reward_risk": 1.5,
                "invalidation": "x",
                "plan_status": "VALID",
                "rejection_reason": None,
            },
            {
                "run_id": "run-001",
                "record_type": "trade_plan",
                "plan_id": "p2",
                "timestamp": 1705334520,
                "symbol": "TSLA",
                "timeframe": "2",
                "replay_date": "2024-01-15",
                "candle_index": 2,
                "setup_type": "FAILED_LTP",
                "watch_type": "FAILED_LTP_WATCH",
                "grade": "B",
                "source_candle_index": 1,
                "direction": "short",
                "entry_trigger": 100.0,
                "stop": 102.0,
                "risk": 2.0,
                "target_1_5r": 97.0,
                "reward_risk": 1.5,
                "invalidation": "x",
                "plan_status": "VALID",
                "rejection_reason": None,
            },
        ],
    )
    _write_jsonl(run_dir / "rejected_trade_plans.jsonl", [])
    _write_jsonl(
        run_dir / "trade_outcomes.jsonl",
        [
            {
                "run_id": "run-001",
                "record_type": "trade_outcome",
                "plan_id": "p1",
                "symbol": "TSLA",
                "timeframe": "2",
                "replay_date": "2024-01-15",
                "entry_candle_index": 1,
                "entry_timestamp": 1705334400,
                "exit_candle_index": 2,
                "exit_timestamp": 1705334520,
                "exit_price": 103.0,
                "exit_reason": "target hit",
                "realized_r": 1.5,
                "outcome_status": "TARGET_BEFORE_STOP",
                "counts_as_win": True,
                "counts_as_loss": False,
                "audit_trail": ["a", "b"],
            },
            {
                "run_id": "run-001",
                "record_type": "trade_outcome",
                "plan_id": "p2",
                "symbol": "TSLA",
                "timeframe": "2",
                "replay_date": "2024-01-15",
                "entry_candle_index": 2,
                "entry_timestamp": 1705334520,
                "exit_candle_index": 3,
                "exit_timestamp": 1705334640,
                "exit_price": None,
                "exit_reason": "both touched",
                "realized_r": None,
                "outcome_status": "AMBIGUOUS_BOTH_TOUCHED",
                "counts_as_win": False,
                "counts_as_loss": False,
                "audit_trail": ["a", "b"],
            },
        ],
    )
    (run_dir / "day_runner_summary.json").write_text(
        json.dumps(
            {
                "run_id": "run-001",
                "valid_trade_plan_count": 2,
                "rejected_trade_plan_count": 0,
                "trade_outcome_count": 2,
                "simulated_trade_plan_count": 2,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _decision(**overrides) -> HumanReviewDecision:
    base = dict(
        decision_id="run-001:p1:decision-1",
        review_id="run-001:p1",
        plan_id="p1",
        outcome_id="p1",
        label=ReviewDecisionLabel.VALID_WIN,
        reviewer="reviewer-1",
        timestamp="2026-06-29T12:00:00Z",
        notes="Looks correct.",
    )
    base.update(overrides)
    return HumanReviewDecision(**base)


def _revision(**overrides) -> HumanReviewRevision:
    base = dict(
        revision_id="run-001:p1:revision-1",
        original_decision_id="run-001:p1:decision-1",
        review_id="run-001:p1",
        revised_label=ReviewDecisionLabel.NEEDS_MORE_INFO,
        reviewer="reviewer-2",
        timestamp="2026-06-29T12:10:00Z",
        revision_reason="Need more chart context.",
        notes="Need wider market context.",
        revision_sequence=1,
        previous_effective_decision_id="run-001:p1:decision-1",
    )
    base.update(overrides)
    return HumanReviewRevision(**base)


class TestReviewExport:
    def test_export_works_with_no_decisions_yet(self, tmp_path):
        run_dir = tmp_path / "run-001"
        _write_run_dir(run_dir)
        build_statistics(run_dir)
        build_daily_report(run_dir)
        build_daily_review_queue(run_dir)

        result = build_human_review_export(run_dir)

        assert result.dashboard_payload["total_items"] == 2
        assert len(result.dashboard_payload["unreviewed_items"]) == 2
        assert result.dashboard_payload["reviewed_items"] == []
        assert result.items_payload["items"][0]["current_review_status"] == ReviewExportStatus.UNREVIEWED
        assert result.artifacts.review_dashboard_md_path.exists()
        assert result.artifacts.review_items_json_path.exists()

    def test_export_works_with_decisions(self, tmp_path):
        run_dir = tmp_path / "run-001"
        _write_run_dir(run_dir)
        build_statistics(run_dir)
        build_daily_report(run_dir)
        build_daily_review_queue(run_dir)
        append_human_review_decision(run_dir, _decision())

        result = build_human_review_export(run_dir)
        items_by_id = {item["review_queue_id"]: item for item in result.items_payload["items"]}

        assert items_by_id["run-001:p1"]["latest_effective_label"] == ReviewDecisionLabel.VALID_WIN
        assert items_by_id["run-001:p1"]["current_review_status"] == ReviewExportStatus.REVIEWED
        assert items_by_id["run-001:p2"]["current_review_status"] == ReviewExportStatus.UNREVIEWED
        assert len(result.dashboard_payload["reviewed_items"]) == 1

    def test_export_works_with_revisions_and_shows_effective_latest_label(self, tmp_path):
        run_dir = tmp_path / "run-001"
        _write_run_dir(run_dir)
        build_statistics(run_dir)
        build_daily_report(run_dir)
        build_daily_review_queue(run_dir)
        append_human_review_decision(run_dir, _decision())
        append_human_review_revision(run_dir, _revision())

        result = build_human_review_export(run_dir)
        item = next(item for item in result.items_payload["items"] if item["review_queue_id"] == "run-001:p1")

        assert item["latest_effective_label"] == ReviewDecisionLabel.NEEDS_MORE_INFO
        assert item["current_review_status"] == ReviewExportStatus.NEEDS_MORE_INFO
        assert item["revision_count"] == 1
        assert item["notes"] == "Need wider market context."
        assert len(result.dashboard_payload["needs_more_info_items"]) == 1

    def test_missing_optional_decision_and_revision_files_are_safe(self, tmp_path):
        run_dir = tmp_path / "run-001"
        _write_run_dir(run_dir)
        build_statistics(run_dir)
        build_daily_report(run_dir)
        build_daily_review_queue(run_dir)

        result = build_human_review_export(run_dir)

        assert (run_dir / "human_review_decisions.jsonl").exists() is False
        assert (run_dir / "human_review_revisions.jsonl").exists() is False
        assert len(result.items_payload["items"]) == 2

    def test_invalid_queue_or_report_inputs_fail_clearly(self, tmp_path):
        run_dir = tmp_path / "run-bad"
        run_dir.mkdir()
        (run_dir / "daily_report.json").write_text(
            json.dumps({"report_status": "invalid"}, indent=2) + "\n",
            encoding="utf-8",
        )
        with pytest.raises(HumanReviewQueueError, match="daily report_status='valid'"):
            build_human_review_export(run_dir)
