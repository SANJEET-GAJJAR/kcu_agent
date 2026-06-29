"""Unit tests for Phase 6C deterministic aggregate statistics."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.statistics import StatisticsInputError, build_aggregate_statistics


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_day_stats(
    run_dir: Path,
    *,
    run_id: str,
    passed: bool = True,
    summary: dict | None = None,
    by_setup: dict | None = None,
    by_direction: dict | None = None,
    by_grade: dict | None = None,
    errors: list[str] | None = None,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        run_dir / "stats_integrity_report.json",
        {
            "run_id": run_id,
            "passed": passed,
            "errors": list(errors or []),
            "valid_trade_plan_count": 0,
            "rejected_trade_plan_count": 0,
            "trade_outcome_count": 0,
            "summary_valid_trade_plan_count": 0,
            "summary_rejected_trade_plan_count": 0,
            "summary_trade_outcome_count": 0,
            "summary_simulated_trade_plan_count": 0,
        },
    )
    if not passed:
        return
    _write_json(run_dir / "stats_summary.json", summary or {})
    _write_json(run_dir / "stats_by_setup.json", by_setup or {})
    _write_json(run_dir / "stats_by_direction.json", by_direction or {})
    _write_json(run_dir / "stats_by_grade.json", by_grade or {})


def _summary(
    *,
    run_id: str,
    total_plans: int,
    valid_plans: int,
    rejected_plans: int,
    simulated_trades: int,
    wins: int,
    losses: int,
    ambiguous: int,
    unresolved: int,
    win_rate: float | None,
    average_realized_r: float | None,
    total_realized_r: float,
    best_trade: dict | None,
    worst_trade: dict | None,
) -> dict:
    return {
        "run_id": run_id,
        "total_plans": total_plans,
        "valid_plans": valid_plans,
        "rejected_plans": rejected_plans,
        "simulated_trades": simulated_trades,
        "wins": wins,
        "losses": losses,
        "ambiguous": ambiguous,
        "unresolved": unresolved,
        "win_rate": win_rate,
        "average_realized_r": average_realized_r,
        "total_realized_r": total_realized_r,
        "best_trade": best_trade,
        "worst_trade": worst_trade,
    }


class TestStatisticsAggregate:
    def test_multiple_valid_days_aggregate_correctly(self, tmp_path):
        run_a = tmp_path / "run-a"
        run_b = tmp_path / "run-b"
        output_dir = tmp_path / "aggregate"

        _write_day_stats(
            run_a,
            run_id="run-a",
            summary=_summary(
                run_id="run-a",
                total_plans=4,
                valid_plans=3,
                rejected_plans=1,
                simulated_trades=3,
                wins=1,
                losses=0,
                ambiguous=1,
                unresolved=1,
                win_rate=1.0,
                average_realized_r=1.5,
                total_realized_r=1.5,
                best_trade={
                    "plan_id": "p1",
                    "realized_r": 1.5,
                    "outcome_status": "TARGET_BEFORE_STOP",
                },
                worst_trade={
                    "plan_id": "p1",
                    "realized_r": 1.5,
                    "outcome_status": "TARGET_BEFORE_STOP",
                },
            ),
            by_setup={
                "FAILED_LTP": {
                    "total_plans": 4,
                    "valid_plans": 3,
                    "rejected_plans": 1,
                    "simulated_trades": 3,
                    "wins": 1,
                    "losses": 0,
                    "ambiguous": 1,
                    "unresolved": 1,
                    "win_rate": 1.0,
                    "average_realized_r": 1.5,
                    "total_realized_r": 1.5,
                    "best_trade": {
                        "plan_id": "p1",
                        "realized_r": 1.5,
                        "outcome_status": "TARGET_BEFORE_STOP",
                    },
                    "worst_trade": {
                        "plan_id": "p1",
                        "realized_r": 1.5,
                        "outcome_status": "TARGET_BEFORE_STOP",
                    },
                }
            },
            by_direction={
                "long": {
                    "total_plans": 2,
                    "valid_plans": 2,
                    "rejected_plans": 0,
                    "simulated_trades": 2,
                    "wins": 1,
                    "losses": 0,
                    "ambiguous": 0,
                    "unresolved": 1,
                    "win_rate": 1.0,
                    "average_realized_r": 1.5,
                    "total_realized_r": 1.5,
                    "best_trade": {
                        "plan_id": "p1",
                        "realized_r": 1.5,
                        "outcome_status": "TARGET_BEFORE_STOP",
                    },
                    "worst_trade": {
                        "plan_id": "p1",
                        "realized_r": 1.5,
                        "outcome_status": "TARGET_BEFORE_STOP",
                    },
                },
                "short": {
                    "total_plans": 1,
                    "valid_plans": 1,
                    "rejected_plans": 0,
                    "simulated_trades": 1,
                    "wins": 0,
                    "losses": 0,
                    "ambiguous": 1,
                    "unresolved": 0,
                    "win_rate": None,
                    "average_realized_r": None,
                    "total_realized_r": 0.0,
                    "best_trade": None,
                    "worst_trade": None,
                },
            },
            by_grade={
                "A": {
                    "total_plans": 1,
                    "valid_plans": 1,
                    "rejected_plans": 0,
                    "simulated_trades": 1,
                    "wins": 1,
                    "losses": 0,
                    "ambiguous": 0,
                    "unresolved": 0,
                    "win_rate": 1.0,
                    "average_realized_r": 1.5,
                    "total_realized_r": 1.5,
                    "best_trade": {
                        "plan_id": "p1",
                        "realized_r": 1.5,
                        "outcome_status": "TARGET_BEFORE_STOP",
                    },
                    "worst_trade": {
                        "plan_id": "p1",
                        "realized_r": 1.5,
                        "outcome_status": "TARGET_BEFORE_STOP",
                    },
                }
            },
        )
        _write_day_stats(
            run_b,
            run_id="run-b",
            summary=_summary(
                run_id="run-b",
                total_plans=2,
                valid_plans=2,
                rejected_plans=0,
                simulated_trades=2,
                wins=0,
                losses=2,
                ambiguous=0,
                unresolved=0,
                win_rate=0.0,
                average_realized_r=-1.0,
                total_realized_r=-2.0,
                best_trade={
                    "plan_id": "p9",
                    "realized_r": -1.0,
                    "outcome_status": "STOP_BEFORE_TARGET",
                },
                worst_trade={
                    "plan_id": "p8",
                    "realized_r": -1.0,
                    "outcome_status": "STOP_BEFORE_TARGET",
                },
            ),
            by_setup={
                "REVERSAL": {
                    "total_plans": 2,
                    "valid_plans": 2,
                    "rejected_plans": 0,
                    "simulated_trades": 2,
                    "wins": 0,
                    "losses": 2,
                    "ambiguous": 0,
                    "unresolved": 0,
                    "win_rate": 0.0,
                    "average_realized_r": -1.0,
                    "total_realized_r": -2.0,
                    "best_trade": {
                        "plan_id": "p9",
                        "realized_r": -1.0,
                        "outcome_status": "STOP_BEFORE_TARGET",
                    },
                    "worst_trade": {
                        "plan_id": "p8",
                        "realized_r": -1.0,
                        "outcome_status": "STOP_BEFORE_TARGET",
                    },
                }
            },
            by_direction={
                "short": {
                    "total_plans": 2,
                    "valid_plans": 2,
                    "rejected_plans": 0,
                    "simulated_trades": 2,
                    "wins": 0,
                    "losses": 2,
                    "ambiguous": 0,
                    "unresolved": 0,
                    "win_rate": 0.0,
                    "average_realized_r": -1.0,
                    "total_realized_r": -2.0,
                    "best_trade": {
                        "plan_id": "p9",
                        "realized_r": -1.0,
                        "outcome_status": "STOP_BEFORE_TARGET",
                    },
                    "worst_trade": {
                        "plan_id": "p8",
                        "realized_r": -1.0,
                        "outcome_status": "STOP_BEFORE_TARGET",
                    },
                }
            },
            by_grade={
                "B": {
                    "total_plans": 2,
                    "valid_plans": 2,
                    "rejected_plans": 0,
                    "simulated_trades": 2,
                    "wins": 0,
                    "losses": 2,
                    "ambiguous": 0,
                    "unresolved": 0,
                    "win_rate": 0.0,
                    "average_realized_r": -1.0,
                    "total_realized_r": -2.0,
                    "best_trade": {
                        "plan_id": "p9",
                        "realized_r": -1.0,
                        "outcome_status": "STOP_BEFORE_TARGET",
                    },
                    "worst_trade": {
                        "plan_id": "p8",
                        "realized_r": -1.0,
                        "outcome_status": "STOP_BEFORE_TARGET",
                    },
                }
            },
        )

        result = build_aggregate_statistics([run_b, run_a], output_dir)

        assert result.summary["total_days"] == 2
        assert result.summary["included_days"] == 2
        assert result.summary["skipped_days"] == 0
        assert result.summary["total_plans"] == 6
        assert result.summary["valid_plans"] == 5
        assert result.summary["rejected_plans"] == 1
        assert result.summary["simulated_trades"] == 5
        assert result.summary["wins"] == 1
        assert result.summary["losses"] == 2
        assert result.summary["ambiguous"] == 1
        assert result.summary["unresolved"] == 1
        assert result.summary["win_rate"] == pytest.approx(1 / 3)
        assert result.summary["average_realized_r"] == pytest.approx(-0.1666666667)
        assert result.summary["total_realized_r"] == -0.5
        assert result.summary["best_trade"]["run_id"] == "run-a"
        assert result.summary["worst_trade"]["run_id"] == "run-b"
        assert sorted(result.by_setup) == ["FAILED_LTP", "REVERSAL"]
        assert result.by_direction["short"]["losses"] == 2
        assert result.by_grade["A"]["wins"] == 1
        assert result.report_payload["metadata"]["report_type"] == "aggregate"
        assert result.report_payload["metadata"]["ticker"] is None
        assert result.report_payload["metadata"]["integrity_status"] == "VALID"
        assert result.report_payload["included_days"][0]["run_id"] == "run-a"
        assert "## By Setup" in result.report_markdown
        assert result.artifacts.aggregate_stats_summary_path.exists()
        assert result.artifacts.aggregate_report_json_path.exists()

    def test_invalid_days_are_skipped_and_listed(self, tmp_path):
        valid_run = tmp_path / "run-valid"
        invalid_run = tmp_path / "run-invalid"
        output_dir = tmp_path / "aggregate"

        _write_day_stats(
            valid_run,
            run_id="run-valid",
            summary=_summary(
                run_id="run-valid",
                total_plans=1,
                valid_plans=1,
                rejected_plans=0,
                simulated_trades=1,
                wins=0,
                losses=0,
                ambiguous=1,
                unresolved=0,
                win_rate=None,
                average_realized_r=None,
                total_realized_r=0.0,
                best_trade=None,
                worst_trade=None,
            ),
            by_setup={},
            by_direction={},
            by_grade={},
        )
        _write_day_stats(
            invalid_run,
            run_id="run-invalid",
            passed=False,
            errors=["summary mismatch"],
        )

        result = build_aggregate_statistics([invalid_run, valid_run], output_dir)

        assert result.summary["total_days"] == 2
        assert result.summary["included_days"] == 1
        assert result.summary["skipped_days"] == 1
        assert result.summary["wins"] == 0
        assert result.summary["losses"] == 0
        assert result.report_payload["skipped_days"][0]["run_id"] == "run-invalid"
        assert result.report_payload["skipped_days"][0]["reason"] == "integrity_failed"
        assert "run-invalid: integrity_failed" in result.report_markdown

    def test_empty_aggregate_is_handled_safely(self, tmp_path):
        output_dir = tmp_path / "aggregate-empty"

        result = build_aggregate_statistics([], output_dir)

        assert result.summary["total_days"] == 0
        assert result.summary["included_days"] == 0
        assert result.summary["skipped_days"] == 0
        assert result.summary["win_rate"] is None
        assert result.summary["average_realized_r"] is None
        assert result.summary["best_trade"] is None
        assert result.by_setup == {}
        assert "No included days." in result.report_markdown
        assert "No skipped days." in result.report_markdown
        assert "No records." in result.report_markdown

    def test_duplicate_run_ids_are_skipped_deterministically(self, tmp_path):
        run_a = tmp_path / "a"
        run_b = tmp_path / "b"
        output_dir = tmp_path / "aggregate-dup"

        common_summary = _summary(
            run_id="run-dup",
            total_plans=1,
            valid_plans=1,
            rejected_plans=0,
            simulated_trades=1,
            wins=1,
            losses=0,
            ambiguous=0,
            unresolved=0,
            win_rate=1.0,
            average_realized_r=1.5,
            total_realized_r=1.5,
            best_trade={
                "plan_id": "p1",
                "realized_r": 1.5,
                "outcome_status": "TARGET_BEFORE_STOP",
            },
            worst_trade={
                "plan_id": "p1",
                "realized_r": 1.5,
                "outcome_status": "TARGET_BEFORE_STOP",
            },
        )
        _write_day_stats(
            run_a,
            run_id="run-dup",
            summary=common_summary,
            by_setup={},
            by_direction={},
            by_grade={},
        )
        _write_day_stats(
            run_b,
            run_id="run-dup",
            summary={
                **common_summary,
                "wins": 0,
                "losses": 1,
                "win_rate": 0.0,
                "average_realized_r": -1.0,
                "total_realized_r": -1.0,
                "best_trade": {
                    "plan_id": "p2",
                    "realized_r": -1.0,
                    "outcome_status": "STOP_BEFORE_TARGET",
                },
                "worst_trade": {
                    "plan_id": "p2",
                    "realized_r": -1.0,
                    "outcome_status": "STOP_BEFORE_TARGET",
                },
            },
            by_setup={},
            by_direction={},
            by_grade={},
        )

        result = build_aggregate_statistics([run_b, run_a], output_dir)

        assert result.summary["included_days"] == 1
        assert result.summary["skipped_days"] == 1
        assert result.summary["wins"] == 1
        assert result.summary["losses"] == 0
        assert result.report_payload["included_days"][0]["run_dir"] == str(run_a)
        assert result.report_payload["skipped_days"][0]["run_dir"] == str(run_b)
        assert result.report_payload["skipped_days"][0]["reason"].startswith("duplicate run_id skipped")

    def test_aggregate_reports_can_write_to_canonical_path(self, tmp_path):
        run_a = tmp_path / "run-a"
        run_b = tmp_path / "run-b"
        output_dir = tmp_path / "aggregate"
        report_root = tmp_path / "outputs" / "reports"

        _write_day_stats(
            run_a,
            run_id="run-a",
            summary=_summary(
                run_id="run-a",
                total_plans=1,
                valid_plans=1,
                rejected_plans=0,
                simulated_trades=1,
                wins=1,
                losses=0,
                ambiguous=0,
                unresolved=0,
                win_rate=1.0,
                average_realized_r=1.5,
                total_realized_r=1.5,
                best_trade={
                    "plan_id": "p1",
                    "realized_r": 1.5,
                    "outcome_status": "TARGET_BEFORE_STOP",
                },
                worst_trade={
                    "plan_id": "p1",
                    "realized_r": 1.5,
                    "outcome_status": "TARGET_BEFORE_STOP",
                },
            ),
            by_setup={},
            by_direction={},
            by_grade={},
        )
        _write_day_stats(
            run_b,
            run_id="run-b",
            summary=_summary(
                run_id="run-b",
                total_plans=1,
                valid_plans=1,
                rejected_plans=0,
                simulated_trades=1,
                wins=0,
                losses=1,
                ambiguous=0,
                unresolved=0,
                win_rate=0.0,
                average_realized_r=-1.0,
                total_realized_r=-1.0,
                best_trade={
                    "plan_id": "p2",
                    "realized_r": -1.0,
                    "outcome_status": "STOP_BEFORE_TARGET",
                },
                worst_trade={
                    "plan_id": "p2",
                    "realized_r": -1.0,
                    "outcome_status": "STOP_BEFORE_TARGET",
                },
            ),
            by_setup={},
            by_direction={},
            by_grade={},
        )
        (run_a / "trade_plans.jsonl").write_text(
            json.dumps({"symbol": "TSLA"}) + "\n",
            encoding="utf-8",
        )
        (run_b / "trade_plans.jsonl").write_text(
            json.dumps({"symbol": "TSLA"}) + "\n",
            encoding="utf-8",
        )

        result = build_aggregate_statistics(
            [run_b, run_a],
            output_dir,
            report_root=report_root,
            range_or_batch_id="2024-01-batch",
            generated_at="2026-06-29T12:00:00Z",
        )

        canonical_dir = report_root / "aggregate" / "TSLA" / "2024-01-batch"
        assert result.artifacts.canonical_aggregate_report_json_path == canonical_dir / "aggregate_report.json"
        assert result.artifacts.canonical_aggregate_report_md_path == canonical_dir / "aggregate_report.md"
        assert (canonical_dir / "aggregate_report.json").exists()
        assert (canonical_dir / "aggregate_report.md").exists()
        payload = json.loads((canonical_dir / "aggregate_report.json").read_text(encoding="utf-8"))
        assert payload["metadata"]["ticker"] == "TSLA"
        assert payload["metadata"]["report_type"] == "aggregate"
        assert payload["metadata"]["generated_at"] == "2026-06-29T12:00:00Z"
        assert payload["metadata"]["source_stats_path"] == [
            str((run_a / "stats_summary.json").resolve()),
            str((run_b / "stats_summary.json").resolve()),
        ]

    def test_missing_valid_day_artifact_fails_clearly(self, tmp_path):
        run_dir = tmp_path / "run-missing"
        output_dir = tmp_path / "aggregate"
        _write_day_stats(
            run_dir,
            run_id="run-missing",
            summary=_summary(
                run_id="run-missing",
                total_plans=1,
                valid_plans=1,
                rejected_plans=0,
                simulated_trades=1,
                wins=1,
                losses=0,
                ambiguous=0,
                unresolved=0,
                win_rate=1.0,
                average_realized_r=1.5,
                total_realized_r=1.5,
                best_trade={
                    "plan_id": "p1",
                    "realized_r": 1.5,
                    "outcome_status": "TARGET_BEFORE_STOP",
                },
                worst_trade={
                    "plan_id": "p1",
                    "realized_r": 1.5,
                    "outcome_status": "TARGET_BEFORE_STOP",
                },
            ),
            by_setup={},
            by_direction={},
            by_grade={},
        )
        (run_dir / "stats_by_grade.json").unlink()

        with pytest.raises(StatisticsInputError, match="statistics by grade file not found"):
            build_aggregate_statistics([run_dir], output_dir)
