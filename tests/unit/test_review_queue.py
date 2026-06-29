"""Unit tests for Phase 7A human review queue."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.review import HumanReviewQueueError, build_daily_review_queue
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
    _write_jsonl(
        run_dir / "rejected_trade_plans.jsonl",
        [
            {
                "run_id": "run-001",
                "record_type": "rejected_trade_plan",
                "plan_id": "p3",
                "timestamp": 1705334640,
                "symbol": "TSLA",
                "timeframe": "2",
                "replay_date": "2024-01-15",
                "candle_index": 3,
                "setup_type": "CHOP",
                "watch_type": "CHOP",
                "grade": None,
                "source_candle_index": 2,
                "direction": "unknown",
                "entry_trigger": None,
                "stop": None,
                "risk": None,
                "target_1_5r": None,
                "reward_risk": None,
                "invalidation": "x",
                "plan_status": "REJECTED_NOT_TRADABLE",
                "rejection_reason": "not tradable",
            },
        ],
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
                "rejected_trade_plan_count": 1,
                "trade_outcome_count": 2,
                "simulated_trade_plan_count": 2,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


class TestReviewQueue:
    def test_daily_review_queue_is_built_deterministically(self, tmp_path):
        run_dir = tmp_path / "run-001"
        _write_run_dir(run_dir)
        build_statistics(run_dir)
        build_daily_report(run_dir)

        result_a = build_daily_review_queue(run_dir)
        snapshot_a = {
            "queue": result_a.artifacts.review_queue_path.read_text(encoding="utf-8"),
            "summary": result_a.artifacts.review_summary_path.read_text(encoding="utf-8"),
        }
        result_b = build_daily_review_queue(run_dir)
        snapshot_b = {
            "queue": result_b.artifacts.review_queue_path.read_text(encoding="utf-8"),
            "summary": result_b.artifacts.review_summary_path.read_text(encoding="utf-8"),
        }

        assert snapshot_a == snapshot_b
        assert len(result_a.entries) == 2
        assert result_a.summary["review_entry_count"] == 2
        assert result_a.summary["pending_review_count"] == 2
        assert result_a.entries[0].review_id == "run-001:p1"
        assert result_a.entries[1].review_id == "run-001:p2"

    def test_rejected_plans_are_not_in_review_queue(self, tmp_path):
        run_dir = tmp_path / "run-001"
        _write_run_dir(run_dir)
        build_statistics(run_dir)
        build_daily_report(run_dir)

        result = build_daily_review_queue(run_dir)

        assert [entry.plan_id for entry in result.entries] == ["p1", "p2"]
        assert all(entry.plan_id != "p3" for entry in result.entries)

    def test_invalid_daily_report_is_rejected(self, tmp_path):
        run_dir = tmp_path / "run-invalid"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "daily_report.json").write_text(
            json.dumps(
                {
                    "run_id": "run-invalid",
                    "report_status": "invalid",
                    "metadata": {
                        "ticker": "TSLA",
                        "date": "2024-01-15",
                        "run_id": "run-invalid",
                        "report_type": "daily",
                        "generated_at": "2026-06-29T12:00:00Z",
                        "source_stats_path": str(run_dir),
                        "integrity_status": "INVALID",
                    },
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        with pytest.raises(HumanReviewQueueError, match="report_status='valid'"):
            build_daily_review_queue(run_dir)

    def test_canonical_daily_review_queue_path_is_supported(self, tmp_path):
        run_dir = tmp_path / "run-001"
        report_root = tmp_path / "outputs" / "reports"
        _write_run_dir(run_dir)
        build_statistics(run_dir)
        build_daily_report(run_dir, report_root=report_root)

        result = build_daily_review_queue(
            run_dir,
            report_root=report_root,
            generated_at="2026-06-29T12:00:00Z",
        )

        canonical_dir = report_root / "daily" / "TSLA" / "2024-01-15" / "run-001"
        assert result.artifacts.canonical_review_queue_path == canonical_dir / "human_review_queue.jsonl"
        assert result.artifacts.canonical_review_summary_path == canonical_dir / "human_review_summary.json"
        assert (canonical_dir / "human_review_queue.jsonl").exists()
        assert (canonical_dir / "human_review_summary.json").exists()
        summary = json.loads((canonical_dir / "human_review_summary.json").read_text(encoding="utf-8"))
        assert summary["ticker"] == "TSLA"
        assert summary["date"] == "2024-01-15"
