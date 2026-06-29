"""Unit tests for Phase 7C human review revisions."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.review import (
    HumanReviewDecision,
    HumanReviewQueueError,
    HumanReviewRevision,
    ReviewDecisionLabel,
    append_human_review_decision,
    append_human_review_revision,
    build_daily_review_queue,
    load_human_review_decisions,
    load_human_review_revisions,
    resolve_human_review_decision_state,
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
            }
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
            }
        ],
    )
    (run_dir / "day_runner_summary.json").write_text(
        json.dumps(
            {
                "run_id": "run-001",
                "valid_trade_plan_count": 1,
                "rejected_trade_plan_count": 0,
                "trade_outcome_count": 1,
                "simulated_trade_plan_count": 1,
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
        revised_label=ReviewDecisionLabel.BAD_TRADE,
        reviewer="reviewer-2",
        timestamp="2026-06-29T12:10:00Z",
        revision_reason="Closer inspection showed poor execution.",
        notes="Entry was late.",
        revision_sequence=1,
        previous_effective_decision_id="run-001:p1:decision-1",
    )
    base.update(overrides)
    return HumanReviewRevision(**base)


class TestReviewRevision:
    def test_valid_revision_writes_and_original_decision_remains_immutable(self, tmp_path):
        run_dir = tmp_path / "run-001"
        _write_run_dir(run_dir)
        build_statistics(run_dir)
        build_daily_report(run_dir)
        build_daily_review_queue(run_dir)
        decision_path = append_human_review_decision(run_dir, _decision())
        original_snapshot = decision_path.read_text(encoding="utf-8")

        revision_path = append_human_review_revision(run_dir, _revision())
        loaded_revisions = load_human_review_revisions(revision_path)

        assert decision_path.read_text(encoding="utf-8") == original_snapshot
        assert revision_path.name == "human_review_revisions.jsonl"
        assert len(loaded_revisions) == 1
        assert loaded_revisions[0].revised_label == ReviewDecisionLabel.BAD_TRADE

    def test_revision_referencing_missing_decision_fails(self, tmp_path):
        run_dir = tmp_path / "run-001"
        _write_run_dir(run_dir)
        build_statistics(run_dir)
        build_daily_report(run_dir)
        build_daily_review_queue(run_dir)
        append_human_review_decision(run_dir, _decision())

        with pytest.raises(HumanReviewQueueError, match="Missing original decision reference"):
            append_human_review_revision(
                run_dir,
                _revision(original_decision_id="missing"),
            )

    def test_invalid_revised_label_fails(self, tmp_path):
        run_dir = tmp_path / "run-001"
        _write_run_dir(run_dir)
        build_statistics(run_dir)
        build_daily_report(run_dir)
        build_daily_review_queue(run_dir)
        append_human_review_decision(run_dir, _decision())

        with pytest.raises(HumanReviewQueueError, match="Invalid human review revision"):
            append_human_review_revision(
                run_dir,
                _revision(revised_label="BAD_LABEL"),
            )

    def test_effective_decision_resolves_deterministically_with_multiple_revisions(self, tmp_path):
        run_dir = tmp_path / "run-001"
        _write_run_dir(run_dir)
        build_statistics(run_dir)
        build_daily_report(run_dir)
        build_daily_review_queue(run_dir)
        append_human_review_decision(run_dir, _decision())
        append_human_review_revision(run_dir, _revision())
        append_human_review_revision(
            run_dir,
            _revision(
                revision_id="run-001:p1:revision-2",
                revised_label=ReviewDecisionLabel.WRONG_CONTEXT,
                reviewer="reviewer-3",
                timestamp="2026-06-29T12:20:00Z",
                revision_reason="Context override after second pass.",
                revision_sequence=2,
                previous_effective_decision_id="run-001:p1:revision-1",
            ),
        )

        state = resolve_human_review_decision_state(run_dir, "run-001:p1")

        assert state.original_decision.label == ReviewDecisionLabel.VALID_WIN
        assert [item.revision_id for item in state.revisions] == [
            "run-001:p1:revision-1",
            "run-001:p1:revision-2",
        ]
        assert state.effective_decision.decision_id == "run-001:p1:revision-2"
        assert state.effective_decision.label == ReviewDecisionLabel.WRONG_CONTEXT
        assert [item.decision_id for item in state.revision_history] == [
            "run-001:p1:decision-1",
            "run-001:p1:revision-1",
            "run-001:p1:revision-2",
        ]

    def test_revision_history_can_be_loaded(self, tmp_path):
        run_dir = tmp_path / "run-001"
        _write_run_dir(run_dir)
        build_statistics(run_dir)
        build_daily_report(run_dir)
        build_daily_review_queue(run_dir)
        append_human_review_decision(run_dir, _decision())
        append_human_review_revision(run_dir, _revision())

        loaded_decisions = load_human_review_decisions(run_dir / "human_review_decisions.jsonl")
        loaded_revisions = load_human_review_revisions(run_dir / "human_review_revisions.jsonl")
        state = resolve_human_review_decision_state(
            run_dir,
            "run-001:p1",
            decisions=loaded_decisions,
            revisions=loaded_revisions,
        )

        assert len(loaded_decisions) == 1
        assert len(loaded_revisions) == 1
        assert state.effective_decision.label == ReviewDecisionLabel.BAD_TRADE
