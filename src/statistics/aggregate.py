"""Phase 6C deterministic aggregate statistics and reporting."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .core import StatisticsInputError
from .reporting import (
    DEFAULT_GENERATED_AT,
    _optional_string,
    _write_optional_copy,
    _write_optional_text,
)


@dataclass(frozen=True)
class AggregateStatisticsArtifacts:
    """Filesystem outputs produced by the Phase 6C aggregate layer."""

    output_dir: Path
    aggregate_stats_summary_path: Path
    aggregate_by_setup_path: Path
    aggregate_by_direction_path: Path
    aggregate_by_grade_path: Path
    aggregate_report_md_path: Path
    aggregate_report_json_path: Path
    canonical_aggregate_report_md_path: Path | None
    canonical_aggregate_report_json_path: Path | None


@dataclass
class AggregateStatisticsResult:
    """In-memory aggregate payloads plus filesystem artifact paths."""

    summary: dict[str, Any]
    by_setup: dict[str, dict[str, Any]]
    by_direction: dict[str, dict[str, Any]]
    by_grade: dict[str, dict[str, Any]]
    report_payload: dict[str, Any]
    report_markdown: str
    artifacts: AggregateStatisticsArtifacts


def build_aggregate_statistics(
    run_dirs: list[Path | str],
    output_dir: Path | str,
    *,
    report_root: Path | str | None = None,
    ticker: str | None = None,
    range_or_batch_id: str | None = None,
    generated_at: str | None = None,
) -> AggregateStatisticsResult:
    """Aggregate multiple completed day-run statistics into deterministic outputs."""
    normalized_run_dirs = sorted({Path(run_dir) for run_dir in run_dirs}, key=lambda p: str(p))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    canonical_ticker = _resolve_aggregate_ticker(normalized_run_dirs, explicit_ticker=ticker)
    canonical_dir = _build_canonical_aggregate_dir(
        report_root,
        ticker=canonical_ticker,
        range_or_batch_id=range_or_batch_id,
    )

    artifacts = AggregateStatisticsArtifacts(
        output_dir=output_dir,
        aggregate_stats_summary_path=output_dir / "aggregate_stats_summary.json",
        aggregate_by_setup_path=output_dir / "aggregate_by_setup.json",
        aggregate_by_direction_path=output_dir / "aggregate_by_direction.json",
        aggregate_by_grade_path=output_dir / "aggregate_by_grade.json",
        aggregate_report_md_path=output_dir / "aggregate_report.md",
        aggregate_report_json_path=output_dir / "aggregate_report.json",
        canonical_aggregate_report_md_path=(
            canonical_dir / "aggregate_report.md" if canonical_dir is not None else None
        ),
        canonical_aggregate_report_json_path=(
            canonical_dir / "aggregate_report.json" if canonical_dir is not None else None
        ),
    )

    processed_days: list[dict[str, Any]] = []
    skipped_days: list[dict[str, Any]] = []
    seen_run_ids: dict[str, Path] = {}

    for run_dir in normalized_run_dirs:
        integrity = _load_json_object(
            run_dir / "stats_integrity_report.json",
            description="statistics integrity report",
        )
        run_id = _coerce_run_id(integrity.get("run_id"), run_dir=run_dir)
        passed = integrity.get("passed")
        if not isinstance(passed, bool):
            raise StatisticsInputError(
                f"Statistics integrity report must include boolean 'passed': {run_dir}"
            )

        if run_id in seen_run_ids:
            skipped_days.append(
                {
                    "run_id": run_id,
                    "run_dir": str(run_dir),
                    "reason": (
                        "duplicate run_id skipped; "
                        f"kept {seen_run_ids[run_id]}"
                    ),
                }
            )
            continue

        seen_run_ids[run_id] = run_dir

        if not passed:
            skipped_days.append(
                {
                    "run_id": run_id,
                    "run_dir": str(run_dir),
                    "reason": "integrity_failed",
                    "errors": list(integrity.get("errors") or []),
                }
            )
            continue

        summary = _load_json_object(
            run_dir / "stats_summary.json",
            description="statistics summary",
        )
        by_setup = _load_json_object(
            run_dir / "stats_by_setup.json",
            description="statistics by setup",
        )
        by_direction = _load_json_object(
            run_dir / "stats_by_direction.json",
            description="statistics by direction",
        )
        by_grade = _load_json_object(
            run_dir / "stats_by_grade.json",
            description="statistics by grade",
        )
        processed_days.append(
            {
                "run_id": run_id,
                "run_dir": str(run_dir),
                "integrity": integrity,
                "summary": summary,
                "by_setup": by_setup,
                "by_direction": by_direction,
                "by_grade": by_grade,
            }
        )

    summary = _aggregate_summaries(processed_days, skipped_days)
    by_setup = _aggregate_grouped(processed_days, "by_setup")
    by_direction = _aggregate_grouped(processed_days, "by_direction")
    by_grade = _aggregate_grouped(processed_days, "by_grade")
    metadata = {
        "ticker": canonical_ticker,
        "date": None,
        "run_id": None,
        "report_type": "aggregate",
        "generated_at": generated_at or DEFAULT_GENERATED_AT,
        "source_stats_path": [
            str((Path(day["run_dir"]) / "stats_summary.json").resolve())
            for day in processed_days
        ],
        "integrity_status": "VALID",
        "range_or_batch_id": range_or_batch_id,
    }

    report_payload = {
        "aggregate_status": "valid",
        "metadata": metadata,
        "summary": summary,
        "by_setup": by_setup,
        "by_direction": by_direction,
        "by_grade": by_grade,
        "included_days": [
            {"run_id": day["run_id"], "run_dir": day["run_dir"]}
            for day in processed_days
        ],
        "skipped_days": skipped_days,
    }
    report_markdown = _render_aggregate_report(report_payload)

    _write_json(artifacts.aggregate_stats_summary_path, summary)
    _write_json(artifacts.aggregate_by_setup_path, by_setup)
    _write_json(artifacts.aggregate_by_direction_path, by_direction)
    _write_json(artifacts.aggregate_by_grade_path, by_grade)
    _write_json(artifacts.aggregate_report_json_path, report_payload)
    artifacts.aggregate_report_md_path.write_text(report_markdown, encoding="utf-8")
    _write_optional_copy(artifacts.canonical_aggregate_report_json_path, report_payload)
    _write_optional_text(artifacts.canonical_aggregate_report_md_path, report_markdown)

    return AggregateStatisticsResult(
        summary=summary,
        by_setup=by_setup,
        by_direction=by_direction,
        by_grade=by_grade,
        report_payload=report_payload,
        report_markdown=report_markdown,
        artifacts=artifacts,
    )


def _aggregate_summaries(
    processed_days: list[dict[str, Any]],
    skipped_days: list[dict[str, Any]],
) -> dict[str, Any]:
    totals = {
        "total_days": len(processed_days) + len(skipped_days),
        "included_days": len(processed_days),
        "skipped_days": len(skipped_days),
        "total_plans": 0,
        "valid_plans": 0,
        "rejected_plans": 0,
        "simulated_trades": 0,
        "wins": 0,
        "losses": 0,
        "ambiguous": 0,
        "unresolved": 0,
        "total_realized_r": 0.0,
        "best_trade": None,
        "worst_trade": None,
    }
    realized_weight = 0

    for day in processed_days:
        summary = day["summary"]
        totals["total_plans"] += _required_int(summary, "total_plans")
        totals["valid_plans"] += _required_int(summary, "valid_plans")
        totals["rejected_plans"] += _required_int(summary, "rejected_plans")
        totals["simulated_trades"] += _required_int(summary, "simulated_trades")
        totals["wins"] += _required_int(summary, "wins")
        totals["losses"] += _required_int(summary, "losses")
        totals["ambiguous"] += _required_int(summary, "ambiguous")
        totals["unresolved"] += _required_int(summary, "unresolved")
        totals["total_realized_r"] += _required_float(summary, "total_realized_r")

        realized_count = _count_realized_trades(summary)
        realized_weight += realized_count
        totals["best_trade"] = _pick_best_trade(
            totals["best_trade"],
            summary.get("best_trade"),
            run_id=day["run_id"],
        )
        totals["worst_trade"] = _pick_worst_trade(
            totals["worst_trade"],
            summary.get("worst_trade"),
            run_id=day["run_id"],
        )

    totals["total_realized_r"] = round(totals["total_realized_r"], 10)
    totals["win_rate"] = _safe_ratio(totals["wins"], totals["wins"] + totals["losses"])
    totals["average_realized_r"] = (
        round(totals["total_realized_r"] / realized_weight, 10)
        if realized_weight > 0 else None
    )
    return totals


def _count_realized_trades(summary: dict[str, Any]) -> int:
    total_realized = _required_float(summary, "total_realized_r")
    average_realized = summary.get("average_realized_r")
    if average_realized is None:
        return 0
    if not isinstance(average_realized, (int, float)):
        raise StatisticsInputError(
            f"Summary field 'average_realized_r' must be numeric or null, got {average_realized!r}"
        )
    if average_realized == 0:
        wins = _required_int(summary, "wins")
        losses = _required_int(summary, "losses")
        ambiguous = _required_int(summary, "ambiguous")
        unresolved = _required_int(summary, "unresolved")
        simulated = _required_int(summary, "simulated_trades")
        realized_count = simulated - ambiguous - unresolved
        if realized_count < 0:
            raise StatisticsInputError("Derived realized trade count cannot be negative")
        if total_realized != 0:
            raise StatisticsInputError(
                "Summary average_realized_r=0 is inconsistent with non-zero total_realized_r"
            )
        if wins + losses != realized_count:
            raise StatisticsInputError(
                "Summary realized trade count is inconsistent with wins/losses totals"
            )
        return realized_count
    ratio = total_realized / float(average_realized)
    rounded = int(round(ratio))
    if abs(ratio - rounded) > 1e-9:
        raise StatisticsInputError(
            "Summary realized R fields do not imply an integer realized trade count"
        )
    return rounded


def _aggregate_grouped(
    processed_days: list[dict[str, Any]],
    group_key: str,
) -> dict[str, dict[str, Any]]:
    combined: dict[str, list[dict[str, Any]]] = {}
    for day in processed_days:
        grouped = day[group_key]
        if not isinstance(grouped, dict):
            raise StatisticsInputError(f"Grouped statistics must be objects: {day['run_dir']}")
        for bucket_name, bucket_stats in grouped.items():
            if not isinstance(bucket_stats, dict):
                raise StatisticsInputError(
                    f"Grouped statistics bucket must be an object: {day['run_dir']}::{bucket_name}"
                )
            combined.setdefault(str(bucket_name), []).append(bucket_stats)

    results: dict[str, dict[str, Any]] = {}
    for bucket_name in sorted(combined):
        results[bucket_name] = _aggregate_bucket_stats(combined[bucket_name])
    return results


def _aggregate_bucket_stats(bucket_stats_list: list[dict[str, Any]]) -> dict[str, Any]:
    totals = {
        "total_plans": 0,
        "valid_plans": 0,
        "rejected_plans": 0,
        "simulated_trades": 0,
        "wins": 0,
        "losses": 0,
        "ambiguous": 0,
        "unresolved": 0,
        "total_realized_r": 0.0,
        "best_trade": None,
        "worst_trade": None,
    }
    realized_weight = 0

    for stats in bucket_stats_list:
        totals["total_plans"] += _required_int(stats, "total_plans")
        totals["valid_plans"] += _required_int(stats, "valid_plans")
        totals["rejected_plans"] += _required_int(stats, "rejected_plans")
        totals["simulated_trades"] += _required_int(stats, "simulated_trades")
        totals["wins"] += _required_int(stats, "wins")
        totals["losses"] += _required_int(stats, "losses")
        totals["ambiguous"] += _required_int(stats, "ambiguous")
        totals["unresolved"] += _required_int(stats, "unresolved")
        totals["total_realized_r"] += _required_float(stats, "total_realized_r")
        realized_weight += _count_realized_trades(stats)
        totals["best_trade"] = _pick_best_trade(
            totals["best_trade"],
            stats.get("best_trade"),
            run_id=None,
        )
        totals["worst_trade"] = _pick_worst_trade(
            totals["worst_trade"],
            stats.get("worst_trade"),
            run_id=None,
        )

    totals["total_realized_r"] = round(totals["total_realized_r"], 10)
    totals["win_rate"] = _safe_ratio(totals["wins"], totals["wins"] + totals["losses"])
    totals["average_realized_r"] = (
        round(totals["total_realized_r"] / realized_weight, 10)
        if realized_weight > 0 else None
    )
    return totals


def _pick_best_trade(
    current: dict[str, Any] | None,
    candidate: dict[str, Any] | None,
    *,
    run_id: str | None,
) -> dict[str, Any] | None:
    normalized = _normalize_trade(candidate, run_id=run_id)
    if normalized is None:
        return current
    if current is None:
        return normalized
    if (
        normalized["realized_r"],
        normalized.get("run_id") or "",
        normalized["plan_id"],
    ) > (
        current["realized_r"],
        current.get("run_id") or "",
        current["plan_id"],
    ):
        return normalized
    return current


def _pick_worst_trade(
    current: dict[str, Any] | None,
    candidate: dict[str, Any] | None,
    *,
    run_id: str | None,
) -> dict[str, Any] | None:
    normalized = _normalize_trade(candidate, run_id=run_id)
    if normalized is None:
        return current
    if current is None:
        return normalized
    if (
        normalized["realized_r"],
        normalized.get("run_id") or "",
        normalized["plan_id"],
    ) < (
        current["realized_r"],
        current.get("run_id") or "",
        current["plan_id"],
    ):
        return normalized
    return current


def _normalize_trade(
    trade: dict[str, Any] | None,
    *,
    run_id: str | None,
) -> dict[str, Any] | None:
    if trade is None:
        return None
    if not isinstance(trade, dict):
        raise StatisticsInputError(f"Trade summary entry must be an object, got {trade!r}")
    plan_id = trade.get("plan_id")
    outcome_status = trade.get("outcome_status")
    realized_r = trade.get("realized_r")
    if not isinstance(plan_id, str) or not plan_id:
        raise StatisticsInputError(f"Trade summary entry missing valid plan_id: {trade!r}")
    if not isinstance(outcome_status, str) or not outcome_status:
        raise StatisticsInputError(
            f"Trade summary entry missing valid outcome_status: {trade!r}"
        )
    if not isinstance(realized_r, (int, float)):
        raise StatisticsInputError(
            f"Trade summary entry missing numeric realized_r: {trade!r}"
        )
    normalized = {
        "plan_id": plan_id,
        "outcome_status": outcome_status,
        "realized_r": float(realized_r),
    }
    if run_id is not None:
        normalized["run_id"] = run_id
    return normalized


def _render_aggregate_report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Aggregate Report",
        "",
        "## Summary",
        "",
        f"- Total days: {summary['total_days']}",
        f"- Included days: {summary['included_days']}",
        f"- Skipped days: {summary['skipped_days']}",
        f"- Total plans: {summary['total_plans']}",
        f"- Valid plans: {summary['valid_plans']}",
        f"- Rejected plans: {summary['rejected_plans']}",
        f"- Simulated trades: {summary['simulated_trades']}",
        f"- Wins: {summary['wins']}",
        f"- Losses: {summary['losses']}",
        f"- Ambiguous: {summary['ambiguous']}",
        f"- Unresolved: {summary['unresolved']}",
        f"- Win rate: {_format_scalar(summary.get('win_rate'))}",
        f"- Average realized R: {_format_scalar(summary.get('average_realized_r'))}",
        f"- Total realized R: {_format_scalar(summary.get('total_realized_r'))}",
        f"- Best trade: {_format_trade(summary.get('best_trade'))}",
        f"- Worst trade: {_format_trade(summary.get('worst_trade'))}",
        "",
        "## Included Days",
        "",
    ]
    if payload["included_days"]:
        lines.extend(
            f"- {day['run_id']}: {day['run_dir']}"
            for day in payload["included_days"]
        )
    else:
        lines.append("No included days.")

    lines.extend(["", "## Skipped Days", ""])
    if payload["skipped_days"]:
        lines.extend(
            f"- {day['run_id']}: {day['reason']} ({day['run_dir']})"
            for day in payload["skipped_days"]
        )
    else:
        lines.append("No skipped days.")

    lines.extend(["", "## By Setup", ""])
    lines.extend(_render_group(payload["by_setup"]))
    lines.extend(["", "## By Direction", ""])
    lines.extend(_render_group(payload["by_direction"]))
    lines.extend(["", "## By Grade", ""])
    lines.extend(_render_group(payload["by_grade"]))
    lines.append("")
    return "\n".join(lines)


def _render_group(grouped_stats: dict[str, dict[str, Any]]) -> list[str]:
    if not grouped_stats:
        return ["No records."]

    lines: list[str] = []
    for group_name in sorted(grouped_stats):
        stats = grouped_stats[group_name]
        lines.append(
            (
                f"- {group_name}: total={stats['total_plans']}, "
                f"valid={stats['valid_plans']}, rejected={stats['rejected_plans']}, "
                f"simulated={stats['simulated_trades']}, wins={stats['wins']}, "
                f"losses={stats['losses']}, ambiguous={stats['ambiguous']}, "
                f"unresolved={stats['unresolved']}, win_rate={_format_scalar(stats.get('win_rate'))}, "
                f"avg_r={_format_scalar(stats.get('average_realized_r'))}, "
                f"total_r={_format_scalar(stats.get('total_realized_r'))}"
            )
        )
    return lines


def _format_trade(trade: dict[str, Any] | None) -> str:
    if trade is None:
        return "n/a"
    run_id = trade.get("run_id")
    prefix = f"{run_id}/" if isinstance(run_id, str) and run_id else ""
    return (
        f"{prefix}{trade.get('plan_id', 'unknown')} "
        f"({trade.get('outcome_status', 'unknown')}, "
        f"realized_r={_format_scalar(trade.get('realized_r'))})"
    )


def _format_scalar(value: Any) -> str:
    if value is None:
        return "n/a"
    return str(value)


def _build_canonical_aggregate_dir(
    report_root: Path | str | None,
    *,
    ticker: str | None,
    range_or_batch_id: str | None,
) -> Path | None:
    if report_root is None:
        return None
    if ticker is None:
        raise StatisticsInputError(
            "Aggregate report ticker could not be inferred; provide ticker explicitly"
        )
    if not isinstance(range_or_batch_id, str) or not range_or_batch_id:
        raise StatisticsInputError(
            "Canonical aggregate report path requires non-empty range_or_batch_id"
        )
    return Path(report_root) / "aggregate" / ticker / range_or_batch_id


def _resolve_aggregate_ticker(
    run_dirs: list[Path],
    *,
    explicit_ticker: str | None,
) -> str | None:
    if explicit_ticker is not None:
        return explicit_ticker
    inferred: set[str] = set()
    for run_dir in run_dirs:
        ticker = _infer_run_ticker(run_dir)
        if ticker is not None:
            inferred.add(ticker)
    if not inferred:
        return None
    if len(inferred) > 1:
        raise StatisticsInputError(
            f"Aggregate report ticker is ambiguous across runs: {sorted(inferred)}"
        )
    return next(iter(inferred))


def _infer_run_ticker(run_dir: Path) -> str | None:
    for filename in ("trade_plans.jsonl", "rejected_trade_plans.jsonl", "trade_outcomes.jsonl"):
        path = run_dir / filename
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise StatisticsInputError(
                    f"Malformed JSONL record while inferring aggregate ticker at {path}: {exc}"
                ) from exc
            if not isinstance(row, dict):
                raise StatisticsInputError(
                    f"JSONL record while inferring aggregate ticker must be an object: {path}"
                )
            return _optional_string(row.get("symbol"))
    return None


def _coerce_run_id(value: Any, *, run_dir: Path) -> str:
    if not isinstance(value, str) or not value:
        raise StatisticsInputError(
            f"Statistics integrity report missing valid run_id: {run_dir}"
        )
    return value


def _required_int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int):
        raise StatisticsInputError(
            f"Required integer field {key!r} missing or invalid: {value!r}"
        )
    return value


def _required_float(data: dict[str, Any], key: str) -> float:
    value = data.get(key)
    if not isinstance(value, (int, float)):
        raise StatisticsInputError(
            f"Required numeric field {key!r} missing or invalid: {value!r}"
        )
    return float(value)


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 10)


def _load_json_object(path: Path, *, description: str) -> dict[str, Any]:
    if not path.exists():
        raise StatisticsInputError(f"Required {description} file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StatisticsInputError(
            f"Malformed {description} JSON at {path}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise StatisticsInputError(
            f"{description.capitalize()} file must contain a JSON object: {path}"
        )
    return data


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
