"""Unit tests for Phase 7A human review schema."""
from __future__ import annotations

from src.review.schema import ReviewQueueEntry, ReviewQueueStatus


class TestReviewSchema:
    def test_review_queue_entry_round_trips_and_validates(self):
        entry = ReviewQueueEntry(
            review_id="run-001:TSLA_2024-01-15_00001",
            queue_status=ReviewQueueStatus.PENDING,
            created_at="2026-06-29T12:00:00Z",
            run_id="run-001",
            plan_id="TSLA_2024-01-15_00001",
            symbol="TSLA",
            timeframe="2",
            replay_date="2024-01-15",
            setup_type="FAILED_LTP",
            watch_type="FAILED_LTP_WATCH",
            grade="B",
            direction="long",
            plan_status="VALID",
            source_candle_index=0,
            entry_candle_index=1,
            entry_timestamp=1705334400,
            outcome_status="TARGET_BEFORE_STOP",
            exit_reason="target hit",
            realized_r=1.5,
            counts_as_win=True,
            counts_as_loss=False,
            integrity_status="VALID",
            evidence_paths={
                "daily_report_json": "/tmp/daily_report.json",
                "daily_report_md": "/tmp/daily_report.md",
                "trade_plans_jsonl": "/tmp/trade_plans.jsonl",
                "trade_outcomes_jsonl": "/tmp/trade_outcomes.jsonl",
                "stats_summary_json": "/tmp/stats_summary.json",
            },
        )

        assert entry.validate() == []
        clone = ReviewQueueEntry.from_dict(entry.to_dict())
        assert clone.to_dict() == entry.to_dict()

    def test_review_queue_entry_requires_valid_evidence_and_integrity(self):
        entry = ReviewQueueEntry(
            review_id="r1",
            queue_status="BAD",
            created_at="",
            run_id="",
            plan_id="",
            symbol="",
            timeframe="",
            replay_date="",
            setup_type="",
            watch_type="",
            grade=None,
            direction="",
            plan_status="",
            source_candle_index=-1,
            entry_candle_index=-1,
            entry_timestamp=0,
            outcome_status="",
            exit_reason="",
            realized_r=None,
            counts_as_win=False,
            counts_as_loss=False,
            integrity_status="INVALID",
            evidence_paths={},
        )

        errors = entry.validate()
        assert any("queue_status" in error for error in errors)
        assert any("integrity_status" in error for error in errors)
        assert any("evidence_paths missing required keys" in error for error in errors)
