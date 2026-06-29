"""Phase 6A deterministic statistics core for persisted day-run outputs."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.simulator.execution_contract import ExecutionOutcome
from src.simulator.outcome import OutcomeResult
from src.simulator.trade_plan import TradePlan


class StatisticsInputError(Exception):
    """Raised when persisted simulator outputs are missing or malformed."""


@dataclass(frozen=True)
class StatisticsIntegrityReport:
    """Cross-file integrity validation result for one persisted day run."""

    run_id: str | None
    passed: bool
    errors: list[str]
    valid_trade_plan_count: int
    rejected_trade_plan_count: int
    trade_outcome_count: int
    summary_valid_trade_plan_count: int | None
    summary_rejected_trade_plan_count: int | None
    summary_trade_outcome_count: int | None
    summary_simulated_trade_plan_count: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "passed": self.passed,
            "errors": list(self.errors),
            "valid_trade_plan_count": self.valid_trade_plan_count,
            "rejected_trade_plan_count": self.rejected_trade_plan_count,
            "trade_outcome_count": self.trade_outcome_count,
            "summary_valid_trade_plan_count": self.summary_valid_trade_plan_count,
            "summary_rejected_trade_plan_count": self.summary_rejected_trade_plan_count,
            "summary_trade_outcome_count": self.summary_trade_outcome_count,
            "summary_simulated_trade_plan_count": self.summary_simulated_trade_plan_count,
        }


@dataclass(frozen=True)
class StatisticsArtifacts:
    """Filesystem outputs produced by Phase 6A statistics core."""

    run_dir: Path
    stats_integrity_report_path: Path
    stats_summary_path: Path
    stats_by_setup_path: Path
    stats_by_direction_path: Path
    stats_by_grade_path: Path


@dataclass
class StatisticsResult:
    """In-memory statistics plus filesystem artifact paths."""

    integrity_report: StatisticsIntegrityReport
    summary: dict[str, Any]
    by_setup: dict[str, dict[str, Any]]
    by_direction: dict[str, dict[str, Any]]
    by_grade: dict[str, dict[str, Any]]
    artifacts: StatisticsArtifacts


def build_statistics(run_dir: Path | str) -> StatisticsResult:
    """Load persisted day-run outputs, compute deterministic stats, and write JSON."""
    run_dir = Path(run_dir)
    artifacts = StatisticsArtifacts(
        run_dir=run_dir,
        stats_integrity_report_path=run_dir / "stats_integrity_report.json",
        stats_summary_path=run_dir / "stats_summary.json",
        stats_by_setup_path=run_dir / "stats_by_setup.json",
        stats_by_direction_path=run_dir / "stats_by_direction.json",
        stats_by_grade_path=run_dir / "stats_by_grade.json",
    )

    day_summary = _load_summary(run_dir / "day_runner_summary.json")
    valid_plans = _load_trade_plans(run_dir / "trade_plans.jsonl")
    rejected_plans = _load_trade_plans(run_dir / "rejected_trade_plans.jsonl")
    outcomes = _load_outcomes(run_dir / "trade_outcomes.jsonl")

    integrity_report = _build_integrity_report(
        day_summary=day_summary,
        valid_plans=valid_plans,
        rejected_plans=rejected_plans,
        outcomes=outcomes,
    )
    _write_json(artifacts.stats_integrity_report_path, integrity_report.to_dict())
    if not integrity_report.passed:
        raise StatisticsInputError(
            "Statistics integrity failed: " + "; ".join(integrity_report.errors)
        )

    all_plans = sorted(
        valid_plans + rejected_plans,
        key=lambda p: (p.candle_index, p.timestamp, p.plan_id),
    )
    outcomes = sorted(
        outcomes,
        key=lambda o: (
            o.entry_candle_index,
            o.exit_candle_index if o.exit_candle_index is not None else 10**9,
            o.plan_id,
        ),
    )

    outcome_by_plan_id = {o.plan_id: o for o in outcomes}

    summary = _aggregate_plan_and_outcome_stats(
        all_plans,
        outcomes,
        run_id=str(day_summary.get("run_id", "unknown")),
    )
    summary["by_outcome_status"] = _aggregate_by_outcome_status(outcomes)

    by_setup = _aggregate_grouped(
        all_plans,
        outcome_by_plan_id,
        lambda p: p.setup_type,
    )
    by_direction = _aggregate_grouped(
        all_plans,
        outcome_by_plan_id,
        lambda p: p.direction,
    )
    by_grade = _aggregate_grouped(
        all_plans,
        outcome_by_plan_id,
        lambda p: p.grade if p.grade is not None else "NONE",
    )

    _write_json(artifacts.stats_summary_path, summary)
    _write_json(artifacts.stats_by_setup_path, by_setup)
    _write_json(artifacts.stats_by_direction_path, by_direction)
    _write_json(artifacts.stats_by_grade_path, by_grade)

    return StatisticsResult(
        integrity_report=integrity_report,
        summary=summary,
        by_setup=by_setup,
        by_direction=by_direction,
        by_grade=by_grade,
        artifacts=artifacts,
    )


def _load_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise StatisticsInputError(f"Required summary file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StatisticsInputError(f"Malformed summary JSON at {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise StatisticsInputError(f"Summary file must contain a JSON object: {path}")
    return data


def _build_integrity_report(
    *,
    day_summary: dict[str, Any],
    valid_plans: list[TradePlan],
    rejected_plans: list[TradePlan],
    outcomes: list[OutcomeResult],
) -> StatisticsIntegrityReport:
    errors: list[str] = []

    valid_ids = [p.plan_id for p in valid_plans]
    rejected_ids = [p.plan_id for p in rejected_plans]
    all_plan_ids = valid_ids + rejected_ids
    outcome_ids = [o.plan_id for o in outcomes]

    duplicate_plan_ids = sorted(_duplicates(all_plan_ids))
    if duplicate_plan_ids:
        errors.append(f"duplicate plan ids found: {duplicate_plan_ids}")

    duplicate_outcome_ids = sorted(_duplicates(outcome_ids))
    if duplicate_outcome_ids:
        errors.append(
            f"duplicate outcome plan references found: {duplicate_outcome_ids}"
        )

    valid_id_set = set(valid_ids)
    rejected_id_set = set(rejected_ids)
    outcome_id_set = set(outcome_ids)

    missing_outcomes = sorted(valid_id_set - outcome_id_set)
    if missing_outcomes:
        errors.append(
            f"valid trade plans missing outcomes: {missing_outcomes}"
        )

    orphan_outcomes = sorted(outcome_id_set - valid_id_set)
    if orphan_outcomes:
        errors.append(
            f"outcomes reference non-valid trade plans: {orphan_outcomes}"
        )

    rejected_with_outcomes = sorted(rejected_id_set & outcome_id_set)
    if rejected_with_outcomes:
        errors.append(
            f"rejected trade plans must not have outcomes: {rejected_with_outcomes}"
        )

    summary_valid = _summary_int(day_summary, "valid_trade_plan_count")
    summary_rejected = _summary_int(day_summary, "rejected_trade_plan_count")
    summary_outcomes = _summary_int(day_summary, "trade_outcome_count")
    summary_simulated = _summary_int(day_summary, "simulated_trade_plan_count")

    if summary_valid is not None and summary_valid != len(valid_plans):
        errors.append(
            f"summary valid_trade_plan_count={summary_valid} "
            f"does not match file count={len(valid_plans)}"
        )
    if summary_rejected is not None and summary_rejected != len(rejected_plans):
        errors.append(
            f"summary rejected_trade_plan_count={summary_rejected} "
            f"does not match file count={len(rejected_plans)}"
        )
    if summary_outcomes is not None and summary_outcomes != len(outcomes):
        errors.append(
            f"summary trade_outcome_count={summary_outcomes} "
            f"does not match file count={len(outcomes)}"
        )
    if summary_simulated is not None and summary_simulated != len(valid_plans):
        errors.append(
            f"summary simulated_trade_plan_count={summary_simulated} "
            f"does not match valid plan count={len(valid_plans)}"
        )

    if (
        len(valid_plans) == 0
        and len(rejected_plans) == 0
        and len(outcomes) == 0
    ):
        if summary_valid not in (0, None):
            errors.append(
                f"empty run requires summary valid_trade_plan_count=0, got {summary_valid}"
            )
        if summary_rejected not in (0, None):
            errors.append(
                f"empty run requires summary rejected_trade_plan_count=0, got {summary_rejected}"
            )
        if summary_outcomes not in (0, None):
            errors.append(
                f"empty run requires summary trade_outcome_count=0, got {summary_outcomes}"
            )
        if summary_simulated not in (0, None):
            errors.append(
                f"empty run requires summary simulated_trade_plan_count=0, got {summary_simulated}"
            )

    return StatisticsIntegrityReport(
        run_id=str(day_summary.get("run_id")) if day_summary.get("run_id") is not None else None,
        passed=len(errors) == 0,
        errors=errors,
        valid_trade_plan_count=len(valid_plans),
        rejected_trade_plan_count=len(rejected_plans),
        trade_outcome_count=len(outcomes),
        summary_valid_trade_plan_count=summary_valid,
        summary_rejected_trade_plan_count=summary_rejected,
        summary_trade_outcome_count=summary_outcomes,
        summary_simulated_trade_plan_count=summary_simulated,
    )


def _load_trade_plans(path: Path) -> list[TradePlan]:
    return [
        _parse_trade_plan(path, lineno, line)
        for lineno, line in _read_jsonl_lines(path)
    ]


def _load_outcomes(path: Path) -> list[OutcomeResult]:
    return [
        _parse_outcome(path, lineno, line)
        for lineno, line in _read_jsonl_lines(path)
    ]


def _read_jsonl_lines(path: Path) -> list[tuple[int, dict[str, Any]]]:
    if not path.exists():
        raise StatisticsInputError(f"Required JSONL file not found: {path}")
    rows: list[tuple[int, dict[str, Any]]] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise StatisticsInputError(
                f"Malformed JSONL record at {path}:{lineno}: {exc}"
            ) from exc
        if not isinstance(parsed, dict):
            raise StatisticsInputError(
                f"JSONL record at {path}:{lineno} must be an object"
            )
        rows.append((lineno, parsed))
    return rows


def _parse_trade_plan(path: Path, lineno: int, row: dict[str, Any]) -> TradePlan:
    try:
        plan = TradePlan.from_dict(row)
    except (KeyError, TypeError, ValueError) as exc:
        raise StatisticsInputError(
            f"Malformed trade plan record at {path}:{lineno}: {exc}"
        ) from exc
    errors = plan.validate()
    if errors:
        raise StatisticsInputError(
            f"Invalid trade plan record at {path}:{lineno}: {'; '.join(errors)}"
        )
    return plan


def _parse_outcome(path: Path, lineno: int, row: dict[str, Any]) -> OutcomeResult:
    try:
        outcome = OutcomeResult.from_dict(row)
    except (KeyError, TypeError, ValueError) as exc:
        raise StatisticsInputError(
            f"Malformed trade outcome record at {path}:{lineno}: {exc}"
        ) from exc
    errors = outcome.validate()
    if errors:
        raise StatisticsInputError(
            f"Invalid trade outcome record at {path}:{lineno}: {'; '.join(errors)}"
        )
    return outcome


def _aggregate_grouped(
    plans: list[TradePlan],
    outcome_by_plan_id: dict[str, OutcomeResult],
    key_fn,
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, tuple[list[TradePlan], list[OutcomeResult]]] = {}
    for plan in plans:
        key = str(key_fn(plan))
        bucket_plans, bucket_outcomes = grouped.setdefault(key, ([], []))
        bucket_plans.append(plan)
        if plan.plan_id in outcome_by_plan_id:
            bucket_outcomes.append(outcome_by_plan_id[plan.plan_id])

    return {
        key: _aggregate_plan_and_outcome_stats(bucket_plans, bucket_outcomes)
        for key, (bucket_plans, bucket_outcomes) in sorted(grouped.items(), key=lambda kv: kv[0])
    }


def _aggregate_by_outcome_status(
    outcomes: list[OutcomeResult],
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[OutcomeResult]] = {}
    for outcome in outcomes:
        grouped.setdefault(outcome.outcome_status, []).append(outcome)

    results: dict[str, dict[str, Any]] = {}
    for status, bucket in sorted(grouped.items(), key=lambda kv: kv[0]):
        realized = _realized_values(bucket)
        wins = sum(1 for o in bucket if o.counts_as_win)
        losses = sum(1 for o in bucket if o.counts_as_loss)
        results[status] = {
            "total_plans": len(bucket),
            "valid_plans": len(bucket),
            "rejected_plans": 0,
            "simulated_trades": len(bucket),
            "wins": wins,
            "losses": losses,
            "ambiguous": sum(
                1 for o in bucket
                if o.outcome_status == ExecutionOutcome.AMBIGUOUS_BOTH_TOUCHED
            ),
            "unresolved": sum(
                1 for o in bucket
                if o.outcome_status == ExecutionOutcome.UNRESOLVED_END_OF_REPLAY
            ),
            "win_rate": _safe_ratio(wins, wins + losses),
            "average_realized_r": _average(realized),
            "total_realized_r": round(sum(realized), 10),
            "best_trade": _best_trade(bucket),
            "worst_trade": _worst_trade(bucket),
        }
    return results


def _aggregate_plan_and_outcome_stats(
    plans: list[TradePlan],
    outcomes: list[OutcomeResult],
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    wins = sum(1 for o in outcomes if o.counts_as_win)
    losses = sum(1 for o in outcomes if o.counts_as_loss)
    realized = _realized_values(outcomes)

    stats = {
        "total_plans": len(plans),
        "valid_plans": sum(1 for p in plans if p.is_valid()),
        "rejected_plans": sum(1 for p in plans if not p.is_valid()),
        "simulated_trades": len(outcomes),
        "wins": wins,
        "losses": losses,
        "ambiguous": sum(
            1 for o in outcomes
            if o.outcome_status == ExecutionOutcome.AMBIGUOUS_BOTH_TOUCHED
        ),
        "unresolved": sum(
            1 for o in outcomes
            if o.outcome_status == ExecutionOutcome.UNRESOLVED_END_OF_REPLAY
        ),
        "win_rate": _safe_ratio(wins, wins + losses),
        "average_realized_r": _average(realized),
        "total_realized_r": round(sum(realized), 10),
        "best_trade": _best_trade(outcomes),
        "worst_trade": _worst_trade(outcomes),
    }
    if run_id is not None:
        stats["run_id"] = run_id
    return stats


def _realized_values(outcomes: list[OutcomeResult]) -> list[float]:
    return [o.realized_r for o in outcomes if o.realized_r is not None]


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 10)


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 10)


def _best_trade(outcomes: list[OutcomeResult]) -> dict[str, Any] | None:
    realized = [o for o in outcomes if o.realized_r is not None]
    if not realized:
        return None
    best = max(realized, key=lambda o: (o.realized_r, o.plan_id))
    return {
        "plan_id": best.plan_id,
        "realized_r": best.realized_r,
        "outcome_status": best.outcome_status,
    }


def _worst_trade(outcomes: list[OutcomeResult]) -> dict[str, Any] | None:
    realized = [o for o in outcomes if o.realized_r is not None]
    if not realized:
        return None
    worst = min(realized, key=lambda o: (o.realized_r, o.plan_id))
    return {
        "plan_id": worst.plan_id,
        "realized_r": worst.realized_r,
        "outcome_status": worst.outcome_status,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _duplicates(values: list[str]) -> set[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for value in values:
        if value in seen:
            dupes.add(value)
        seen.add(value)
    return dupes


def _summary_int(summary: dict[str, Any], key: str) -> int | None:
    if key not in summary:
        return None
    value = summary[key]
    if not isinstance(value, int):
        raise StatisticsInputError(
            f"Summary field {key!r} must be an integer when present, got {value!r}"
        )
    return value
