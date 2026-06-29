"""Unit tests for Phase 7B human review decisions."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.review import (
    HumanReviewDecision,
    HumanReviewQueueError,
    ReviewDecisionLabel,
    append_human_review_decision,
    build_daily_review_queue,
    load_human_review_decisions,
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
    _write_jsonl(
        run_dir / "rejected_trade_plans.jsonl",
        [],
    )
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
        decision_id="run-001:p1:reviewer-1",
        review_id="run-001:p1",
        plan_id="p1",
        outcome_id="p1",
        label=ReviewDecisionLabel.VALID_WIN,
        reviewer="reviewer-1",
        timestamp="2026-06-29T12:00:00Z",
        notes="Looks correct.",
        human_setup_label=None,
        policy_exclusion_reason=None,
    )
    base.update(overrides)
    return HumanReviewDecision(**base)


class TestReviewDecision:
    def test_valid_decision_writes_and_loads_back(self, tmp_path):
        run_dir = tmp_path / "run-001"
        _write_run_dir(run_dir)
        build_statistics(run_dir)
        build_daily_report(run_dir)
        build_daily_review_queue(run_dir)

        path = append_human_review_decision(run_dir, _decision())
        loaded = load_human_review_decisions(path)

        assert path.name == "human_review_decisions.jsonl"
        assert len(loaded) == 1
        assert loaded[0].label == ReviewDecisionLabel.VALID_WIN
        assert loaded[0].review_id == "run-001:p1"

    def test_invalid_label_fails(self, tmp_path):
        run_dir = tmp_path / "run-001"
        _write_run_dir(run_dir)
        build_statistics(run_dir)
        build_daily_report(run_dir)
        build_daily_review_queue(run_dir)

        with pytest.raises(HumanReviewQueueError, match="Invalid human review decision"):
            append_human_review_decision(
                run_dir,
                _decision(label="BAD_LABEL"),
            )

    def test_missing_queue_item_reference_fails(self, tmp_path):
        run_dir = tmp_path / "run-001"
        _write_run_dir(run_dir)
        build_statistics(run_dir)
        build_daily_report(run_dir)
        build_daily_review_queue(run_dir)

        with pytest.raises(HumanReviewQueueError, match="Missing queue item reference"):
            append_human_review_decision(
                run_dir,
                _decision(review_id="run-001:missing"),
            )

    def test_duplicate_decision_for_same_review_item_fails_deterministically(self, tmp_path):
        run_dir = tmp_path / "run-001"
        _write_run_dir(run_dir)
        build_statistics(run_dir)
        build_daily_report(run_dir)
        build_daily_review_queue(run_dir)

        append_human_review_decision(run_dir, _decision())
        with pytest.raises(HumanReviewQueueError, match="Duplicate decision for review_id"):
            append_human_review_decision(
                run_dir,
                _decision(decision_id="run-001:p1:reviewer-2"),
            )

    def test_missing_outcome_reference_fails(self, tmp_path):
        run_dir = tmp_path / "run-001"
        _write_run_dir(run_dir)
        build_statistics(run_dir)
        build_daily_report(run_dir)
        build_daily_review_queue(run_dir)

        with pytest.raises(HumanReviewQueueError, match="Missing outcome reference"):
            append_human_review_decision(
                run_dir,
                _decision(outcome_id="missing"),
            )

    def test_decision_can_store_human_setup_label(self, tmp_path):
        run_dir = tmp_path / "run-001"
        _write_run_dir(run_dir)
        build_statistics(run_dir)
        build_daily_report(run_dir)
        build_daily_review_queue(run_dir)

        path = append_human_review_decision(
            run_dir,
            _decision(
                label=ReviewDecisionLabel.BAD_TRADE,
                human_setup_label="REJECTION",
                notes="Looked more like a rejection than FAILED_LTP.",
            ),
        )
        loaded = load_human_review_decisions(path)

        assert loaded[0].human_setup_label == "REJECTION"

    def test_existing_review_loading_remains_backward_compatible(self, tmp_path):
        path = tmp_path / "human_review_decisions.jsonl"
        _write_jsonl(
            path,
            [
                {
                    "decision_id": "d1",
                    "review_id": "r1",
                    "plan_id": "p1",
                    "outcome_id": "p1",
                    "label": ReviewDecisionLabel.VALID_WIN,
                    "reviewer": "reviewer-1",
                    "timestamp": "2026-06-29T12:00:00Z",
                    "notes": "legacy record",
                }
            ],
        )

        loaded = load_human_review_decisions(path)

        assert len(loaded) == 1
        assert loaded[0].human_setup_label is None
        assert loaded[0].policy_exclusion_reason is None
