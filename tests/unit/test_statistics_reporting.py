"""Unit tests for Phase 6B deterministic reporting."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.statistics import StatisticsInputError, build_daily_report, build_statistics


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


class TestStatisticsReporting:
    def test_valid_stats_produce_markdown_and_json_report(self, tmp_path):
        run_dir = tmp_path / "run-001"
        _write_run_dir(run_dir)
        build_statistics(run_dir)

        result_a = build_daily_report(run_dir)
        snapshot_a = {
            "json": result_a.artifacts.daily_report_json_path.read_text(encoding="utf-8"),
            "md": result_a.artifacts.daily_report_md_path.read_text(encoding="utf-8"),
        }
        result_b = build_daily_report(run_dir)
        snapshot_b = {
            "json": result_b.artifacts.daily_report_json_path.read_text(encoding="utf-8"),
            "md": result_b.artifacts.daily_report_md_path.read_text(encoding="utf-8"),
        }

        assert snapshot_a == snapshot_b
        payload = json.loads(snapshot_a["json"])
        assert payload["report_status"] == "valid"
        assert payload["metadata"]["ticker"] == "TSLA"
        assert payload["metadata"]["date"] == "2024-01-15"
        assert payload["metadata"]["run_id"] == "run-001"
        assert payload["metadata"]["report_type"] == "daily"
        assert payload["metadata"]["integrity_status"] == "VALID"
        assert payload["integrity"]["passed"] is True
        assert payload["summary"]["wins"] == 1
        assert payload["summary"]["losses"] == 0
        assert payload["summary"]["ambiguous"] == 1
        assert payload["summary"]["unresolved"] == 1
        assert payload["summary"]["win_rate"] == 1.0
        assert payload["summary"]["average_realized_r"] == 1.5
        assert payload["by_setup"]["FAILED_LTP"]["wins"] == 1
        assert "- Integrity Status: `VALID`" in snapshot_a["md"]
        assert "- Best trade: p1 (TARGET_BEFORE_STOP, realized_r=1.5)" in snapshot_a["md"]

    def test_failed_integrity_produces_invalid_report_without_performance_claims(self, tmp_path):
        run_dir = tmp_path / "run-invalid"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "stats_integrity_report.json").write_text(
            json.dumps(
                {
                    "run_id": "run-invalid",
                    "passed": False,
                    "errors": ["valid trade plans missing outcomes: ['p1']"],
                    "valid_trade_plan_count": 1,
                    "rejected_trade_plan_count": 0,
                    "trade_outcome_count": 0,
                    "summary_valid_trade_plan_count": 1,
                    "summary_rejected_trade_plan_count": 0,
                    "summary_trade_outcome_count": 0,
                    "summary_simulated_trade_plan_count": 1,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        result = build_daily_report(run_dir)
        payload = json.loads(
            result.artifacts.daily_report_json_path.read_text(encoding="utf-8")
        )

        assert payload["report_status"] == "invalid"
        assert payload["metadata"]["report_type"] == "daily"
        assert payload["metadata"]["integrity_status"] == "INVALID"
        assert "summary" not in payload
        assert "Performance metrics are omitted." in payload["message"]
        assert "## Summary" not in result.markdown
        assert "valid trade plans missing outcomes" in result.markdown
        assert "- Integrity Status: `INVALID`" in result.markdown

    def test_empty_valid_day_is_reported_cleanly(self, tmp_path):
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
        build_statistics(run_dir)

        result = build_daily_report(run_dir)
        payload = json.loads(
            result.artifacts.daily_report_json_path.read_text(encoding="utf-8")
        )

        assert payload["report_status"] == "valid"
        assert payload["summary"]["total_plans"] == 0
        assert payload["summary"]["win_rate"] is None
        assert payload["summary"]["best_trade"] is None
        assert payload["by_setup"] == {}
        assert "No records." in result.markdown
        assert "- Best trade: n/a" in result.markdown

    def test_daily_reports_can_write_to_canonical_path(self, tmp_path):
        run_dir = tmp_path / "run-canonical"
        report_root = tmp_path / "outputs" / "reports"
        _write_run_dir(run_dir)
        build_statistics(run_dir)

        result = build_daily_report(
            run_dir,
            report_root=report_root,
            generated_at="2026-06-29T12:00:00Z",
        )

        canonical_dir = report_root / "daily" / "TSLA" / "2024-01-15" / "run-001"
        assert result.artifacts.daily_report_json_path.exists()
        assert result.artifacts.canonical_daily_report_json_path == canonical_dir / "daily_report.json"
        assert result.artifacts.canonical_daily_report_md_path == canonical_dir / "daily_report.md"
        assert (canonical_dir / "daily_report.json").exists()
        assert (canonical_dir / "daily_report.md").exists()
        canonical_payload = json.loads((canonical_dir / "daily_report.json").read_text(encoding="utf-8"))
        assert canonical_payload["metadata"]["ticker"] == "TSLA"
        assert canonical_payload["metadata"]["date"] == "2024-01-15"
        assert canonical_payload["metadata"]["run_id"] == "run-001"
        assert canonical_payload["metadata"]["generated_at"] == "2026-06-29T12:00:00Z"
        assert canonical_payload["metadata"]["source_stats_path"] == str(run_dir.resolve())

    def test_missing_integrity_report_fails_clearly(self, tmp_path):
        run_dir = tmp_path / "run-missing"
        run_dir.mkdir()

        with pytest.raises(StatisticsInputError, match="statistics integrity report file not found"):
            build_daily_report(run_dir)
