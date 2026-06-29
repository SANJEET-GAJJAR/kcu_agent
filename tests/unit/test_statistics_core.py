"""Unit tests for Phase 6A statistics core."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.simulator.execution_contract import ExecutionOutcome
from src.statistics.core import StatisticsInputError, build_statistics


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, separators=(",", ":")) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


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
            {
                "run_id": "run-001",
                "record_type": "trade_plan",
                "plan_id": "p4",
                "timestamp": 1705334760,
                "symbol": "TSLA",
                "timeframe": "2",
                "replay_date": "2024-01-15",
                "candle_index": 4,
                "setup_type": "FAILED_LTP",
                "watch_type": "FAILED_LTP_WATCH",
                "grade": "C",
                "source_candle_index": 3,
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
            {
                "run_id": "run-001",
                "record_type": "trade_outcome",
                "plan_id": "p4",
                "symbol": "TSLA",
                "timeframe": "2",
                "replay_date": "2024-01-15",
                "entry_candle_index": 4,
                "entry_timestamp": 1705334760,
                "exit_candle_index": 5,
                "exit_timestamp": 1705334880,
                "exit_price": None,
                "exit_reason": "unresolved",
                "realized_r": None,
                "outcome_status": "UNRESOLVED_END_OF_REPLAY",
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
                "valid_trade_plan_count": 3,
                "rejected_trade_plan_count": 1,
                "trade_outcome_count": 3,
                "simulated_trade_plan_count": 3,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


class TestStatisticsCore:
    def test_stats_are_deterministic_and_written(self, tmp_path):
        run_dir = tmp_path / "run-001"
        _write_run_dir(run_dir)

        result_a = build_statistics(run_dir)
        snapshot_a = {
            "integrity": result_a.artifacts.stats_integrity_report_path.read_text(encoding="utf-8"),
            "summary": result_a.artifacts.stats_summary_path.read_text(encoding="utf-8"),
            "setup": result_a.artifacts.stats_by_setup_path.read_text(encoding="utf-8"),
            "direction": result_a.artifacts.stats_by_direction_path.read_text(encoding="utf-8"),
            "grade": result_a.artifacts.stats_by_grade_path.read_text(encoding="utf-8"),
        }
        result_b = build_statistics(run_dir)
        snapshot_b = {
            "integrity": result_b.artifacts.stats_integrity_report_path.read_text(encoding="utf-8"),
            "summary": result_b.artifacts.stats_summary_path.read_text(encoding="utf-8"),
            "setup": result_b.artifacts.stats_by_setup_path.read_text(encoding="utf-8"),
            "direction": result_b.artifacts.stats_by_direction_path.read_text(encoding="utf-8"),
            "grade": result_b.artifacts.stats_by_grade_path.read_text(encoding="utf-8"),
        }

        assert snapshot_a == snapshot_b
        assert result_a.integrity_report.passed is True
        assert result_a.summary["total_plans"] == 4
        assert result_a.summary["valid_plans"] == 3
        assert result_a.summary["rejected_plans"] == 1
        assert result_a.summary["simulated_trades"] == 3
        assert result_a.summary["wins"] == 1
        assert result_a.summary["losses"] == 0
        assert result_a.summary["ambiguous"] == 1
        assert result_a.summary["unresolved"] == 1
        assert result_a.summary["win_rate"] == 1.0
        assert result_a.summary["average_realized_r"] == 1.5
        assert result_a.summary["total_realized_r"] == 1.5
        assert result_a.summary["best_trade"]["plan_id"] == "p1"
        assert result_a.summary["worst_trade"]["plan_id"] == "p1"

    def test_ambiguous_and_unresolved_do_not_count_as_wins_or_losses(self, tmp_path):
        run_dir = tmp_path / "run-001"
        _write_run_dir(run_dir)
        result = build_statistics(run_dir)

        by_outcome = result.summary["by_outcome_status"]
        assert by_outcome[ExecutionOutcome.AMBIGUOUS_BOTH_TOUCHED]["wins"] == 0
        assert by_outcome[ExecutionOutcome.AMBIGUOUS_BOTH_TOUCHED]["losses"] == 0
        assert by_outcome[ExecutionOutcome.UNRESOLVED_END_OF_REPLAY]["wins"] == 0
        assert by_outcome[ExecutionOutcome.UNRESOLVED_END_OF_REPLAY]["losses"] == 0

    def test_empty_input_handled_safely(self, tmp_path):
        run_dir = tmp_path / "run-empty"
        run_dir.mkdir()
        _write_jsonl(run_dir / "trade_plans.jsonl", [])
        _write_jsonl(run_dir / "rejected_trade_plans.jsonl", [])
        _write_jsonl(run_dir / "trade_outcomes.jsonl", [])
        (run_dir / "day_runner_summary.json").write_text(
            json.dumps(
                {
                    "run_id": "run-empty",
                    "valid_trade_plan_count": 0,
                    "rejected_trade_plan_count": 0,
                    "trade_outcome_count": 0,
                    "simulated_trade_plan_count": 0,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        result = build_statistics(run_dir)
        assert result.integrity_report.passed is True
        assert result.summary["total_plans"] == 0
        assert result.summary["wins"] == 0
        assert result.summary["losses"] == 0
        assert result.summary["win_rate"] is None
        assert result.summary["average_realized_r"] is None
        assert result.summary["best_trade"] is None
        assert result.by_setup == {}
        assert result.by_direction == {}
        assert result.by_grade == {}

    def test_malformed_records_fail_clearly(self, tmp_path):
        run_dir = tmp_path / "run-bad"
        _write_run_dir(run_dir)
        (run_dir / "trade_outcomes.jsonl").write_text("{bad json\n", encoding="utf-8")

        with pytest.raises(StatisticsInputError, match="Malformed JSONL record"):
            build_statistics(run_dir)

    def test_invalid_records_fail_clearly(self, tmp_path):
        run_dir = tmp_path / "run-invalid"
        _write_run_dir(run_dir)
        _write_jsonl(
            run_dir / "trade_outcomes.jsonl",
            [
                {
                    "plan_id": "",
                    "symbol": "TSLA",
                    "timeframe": "2",
                    "replay_date": "2024-01-15",
                    "entry_candle_index": 1,
                    "entry_timestamp": 1705334400,
                    "exit_candle_index": 2,
                    "exit_timestamp": 1705334520,
                    "exit_price": 103.0,
                    "exit_reason": "",
                    "realized_r": 1.5,
                    "outcome_status": "TARGET_BEFORE_STOP",
                    "counts_as_win": True,
                    "counts_as_loss": False,
                    "audit_trail": [],
                }
            ],
        )

        with pytest.raises(StatisticsInputError, match="Invalid trade outcome record"):
            build_statistics(run_dir)

    def test_missing_outcome_for_valid_plan_fails(self, tmp_path):
        run_dir = tmp_path / "run-missing-outcome"
        _write_run_dir(run_dir)
        _write_jsonl(
            run_dir / "trade_outcomes.jsonl",
            [
                row for row in _read_jsonl(run_dir / "trade_outcomes.jsonl")
                if row["plan_id"] != "p4"
            ],
        )
        with pytest.raises(StatisticsInputError, match="missing outcomes"):
            build_statistics(run_dir)
        report = json.loads((run_dir / "stats_integrity_report.json").read_text(encoding="utf-8"))
        assert report["passed"] is False

    def test_outcome_without_plan_fails(self, tmp_path):
        run_dir = tmp_path / "run-orphan-outcome"
        _write_run_dir(run_dir)
        outcomes = _read_jsonl(run_dir / "trade_outcomes.jsonl")
        outcomes.append(
            {
                "run_id": "run-001",
                "record_type": "trade_outcome",
                "plan_id": "p999",
                "symbol": "TSLA",
                "timeframe": "2",
                "replay_date": "2024-01-15",
                "entry_candle_index": 9,
                "entry_timestamp": 1705335360,
                "exit_candle_index": 10,
                "exit_timestamp": 1705335480,
                "exit_price": 103.0,
                "exit_reason": "orphan outcome",
                "realized_r": 1.5,
                "outcome_status": "TARGET_BEFORE_STOP",
                "counts_as_win": True,
                "counts_as_loss": False,
                "audit_trail": ["a", "b"],
            }
        )
        _write_jsonl(run_dir / "trade_outcomes.jsonl", outcomes)
        with pytest.raises(StatisticsInputError, match="non-valid trade plans"):
            build_statistics(run_dir)

    def test_rejected_plan_with_outcome_fails(self, tmp_path):
        run_dir = tmp_path / "run-rejected-outcome"
        _write_run_dir(run_dir)
        outcomes = _read_jsonl(run_dir / "trade_outcomes.jsonl")
        outcomes.append(
            {
                "run_id": "run-001",
                "record_type": "trade_outcome",
                "plan_id": "p3",
                "symbol": "TSLA",
                "timeframe": "2",
                "replay_date": "2024-01-15",
                "entry_candle_index": 3,
                "entry_timestamp": 1705334640,
                "exit_candle_index": 4,
                "exit_timestamp": 1705334760,
                "exit_price": None,
                "exit_reason": "bad linkage",
                "realized_r": None,
                "outcome_status": "AMBIGUOUS_BOTH_TOUCHED",
                "counts_as_win": False,
                "counts_as_loss": False,
                "audit_trail": ["a", "b"],
            }
        )
        _write_jsonl(run_dir / "trade_outcomes.jsonl", outcomes)
        with pytest.raises(StatisticsInputError, match="must not have outcomes"):
            build_statistics(run_dir)

    def test_duplicate_ids_fail(self, tmp_path):
        run_dir = tmp_path / "run-duplicate-ids"
        _write_run_dir(run_dir)
        plans = _read_jsonl(run_dir / "trade_plans.jsonl")
        plans.append(dict(plans[0]))
        _write_jsonl(run_dir / "trade_plans.jsonl", plans)
        with pytest.raises(StatisticsInputError, match="duplicate plan ids"):
            build_statistics(run_dir)

    def test_duplicate_outcome_plan_references_fail(self, tmp_path):
        run_dir = tmp_path / "run-duplicate-outcomes"
        _write_run_dir(run_dir)
        outcomes = _read_jsonl(run_dir / "trade_outcomes.jsonl")
        dup = dict(outcomes[0])
        dup["exit_reason"] = "duplicate reference"
        outcomes.append(dup)
        _write_jsonl(run_dir / "trade_outcomes.jsonl", outcomes)
        with pytest.raises(StatisticsInputError, match="duplicate outcome plan references"):
            build_statistics(run_dir)

    def test_summary_mismatch_fails(self, tmp_path):
        run_dir = tmp_path / "run-summary-mismatch"
        _write_run_dir(run_dir)
        (run_dir / "day_runner_summary.json").write_text(
            json.dumps(
                {
                    "run_id": "run-001",
                    "valid_trade_plan_count": 99,
                    "rejected_trade_plan_count": 1,
                    "trade_outcome_count": 3,
                    "simulated_trade_plan_count": 3,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        with pytest.raises(StatisticsInputError, match="summary valid_trade_plan_count"):
            build_statistics(run_dir)

    def test_empty_valid_day_passes_only_with_zero_summary(self, tmp_path):
        run_dir = tmp_path / "run-empty-invalid-summary"
        run_dir.mkdir()
        _write_jsonl(run_dir / "trade_plans.jsonl", [])
        _write_jsonl(run_dir / "rejected_trade_plans.jsonl", [])
        _write_jsonl(run_dir / "trade_outcomes.jsonl", [])
        (run_dir / "day_runner_summary.json").write_text(
            json.dumps(
                {
                    "run_id": "run-empty",
                    "valid_trade_plan_count": 1,
                    "rejected_trade_plan_count": 0,
                    "trade_outcome_count": 0,
                    "simulated_trade_plan_count": 0,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        with pytest.raises(StatisticsInputError, match="empty run requires summary"):
            build_statistics(run_dir)
