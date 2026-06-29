"""Phase 6B deterministic reporting layer for persisted statistics artifacts."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .core import StatisticsInputError

DEFAULT_GENERATED_AT = "1970-01-01T00:00:00Z"


@dataclass(frozen=True)
class StatisticsReportArtifacts:
    """Filesystem outputs produced by the Phase 6B reporting layer."""

    run_dir: Path
    stats_integrity_report_path: Path
    stats_summary_path: Path
    stats_by_setup_path: Path
    stats_by_direction_path: Path
    stats_by_grade_path: Path
    daily_report_md_path: Path
    daily_report_json_path: Path
    canonical_daily_report_md_path: Path | None
    canonical_daily_report_json_path: Path | None


@dataclass
class StatisticsReportResult:
    """In-memory daily report plus filesystem artifact paths."""

    payload: dict[str, Any]
    markdown: str
    artifacts: StatisticsReportArtifacts


def build_daily_report(
    run_dir: Path | str,
    *,
    report_root: Path | str | None = None,
    ticker: str | None = None,
    trade_date: str | None = None,
    generated_at: str | None = None,
) -> StatisticsReportResult:
    """Render deterministic daily report artifacts from existing statistics files."""
    run_dir = Path(run_dir)
    metadata_ticker, metadata_date, metadata_run_id = _infer_daily_metadata(
        run_dir,
        ticker=ticker,
        trade_date=trade_date,
        allow_unknown=report_root is None,
    )
    canonical_dir = _build_canonical_daily_dir(
        report_root,
        ticker=metadata_ticker,
        trade_date=metadata_date,
        run_id=metadata_run_id,
    )
    artifacts = StatisticsReportArtifacts(
        run_dir=run_dir,
        stats_integrity_report_path=run_dir / "stats_integrity_report.json",
        stats_summary_path=run_dir / "stats_summary.json",
        stats_by_setup_path=run_dir / "stats_by_setup.json",
        stats_by_direction_path=run_dir / "stats_by_direction.json",
        stats_by_grade_path=run_dir / "stats_by_grade.json",
        daily_report_md_path=run_dir / "daily_report.md",
        daily_report_json_path=run_dir / "daily_report.json",
        canonical_daily_report_md_path=(
            canonical_dir / "daily_report.md" if canonical_dir is not None else None
        ),
        canonical_daily_report_json_path=(
            canonical_dir / "daily_report.json" if canonical_dir is not None else None
        ),
    )

    integrity = _load_json_object(
        artifacts.stats_integrity_report_path,
        description="statistics integrity report",
    )
    passed = integrity.get("passed")
    if not isinstance(passed, bool):
        raise StatisticsInputError(
            "Statistics integrity report must include boolean 'passed'"
        )
    run_id = _coerce_run_id(integrity.get("run_id"))
    if run_id != metadata_run_id:
        raise StatisticsInputError(
            f"Daily report run_id mismatch: inferred={metadata_run_id!r} integrity={run_id!r}"
        )
    metadata = {
        "ticker": metadata_ticker,
        "date": metadata_date,
        "run_id": run_id,
        "report_type": "daily",
        "generated_at": generated_at or DEFAULT_GENERATED_AT,
        "source_stats_path": str(run_dir.resolve()),
        "integrity_status": "VALID" if passed else "INVALID",
    }

    if not passed:
        payload = {
            "run_id": run_id,
            "report_status": "invalid",
            "metadata": metadata,
            "integrity": integrity,
            "message": (
                "Statistics artifacts failed integrity validation. "
                "Performance metrics are omitted."
            ),
        }
        markdown = _render_invalid_report(payload)
    else:
        summary = _load_json_object(
            artifacts.stats_summary_path,
            description="statistics summary",
        )
        by_setup = _load_json_object(
            artifacts.stats_by_setup_path,
            description="statistics by setup",
        )
        by_direction = _load_json_object(
            artifacts.stats_by_direction_path,
            description="statistics by direction",
        )
        by_grade = _load_json_object(
            artifacts.stats_by_grade_path,
            description="statistics by grade",
        )
        payload = {
            "run_id": run_id,
            "report_status": "valid",
            "metadata": metadata,
            "integrity": integrity,
            "summary": summary,
            "by_setup": by_setup,
            "by_direction": by_direction,
            "by_grade": by_grade,
        }
        markdown = _render_valid_report(payload)

    _write_json(artifacts.daily_report_json_path, payload)
    artifacts.daily_report_md_path.write_text(markdown, encoding="utf-8")
    _write_optional_copy(artifacts.canonical_daily_report_json_path, payload)
    _write_optional_text(artifacts.canonical_daily_report_md_path, markdown)

    return StatisticsReportResult(
        payload=payload,
        markdown=markdown,
        artifacts=artifacts,
    )


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


def _build_canonical_daily_dir(
    report_root: Path | str | None,
    *,
    ticker: str,
    trade_date: str,
    run_id: str,
) -> Path | None:
    if report_root is None:
        return None
    return Path(report_root) / "daily" / ticker / trade_date / run_id


def _infer_daily_metadata(
    run_dir: Path,
    *,
    ticker: str | None,
    trade_date: str | None,
    allow_unknown: bool,
) -> tuple[str, str, str]:
    run_id, inferred_ticker, inferred_date = _read_first_record_identity(run_dir)
    resolved_ticker = ticker or inferred_ticker
    resolved_date = trade_date or inferred_date
    if resolved_ticker is None:
        if allow_unknown:
            resolved_ticker = "UNKNOWN"
        else:
            raise StatisticsInputError(
                f"Daily report ticker could not be inferred; provide ticker explicitly: {run_dir}"
            )
    if resolved_date is None:
        if allow_unknown:
            resolved_date = "UNKNOWN"
        else:
            raise StatisticsInputError(
                f"Daily report date could not be inferred; provide trade_date explicitly: {run_dir}"
            )
    if run_id is None:
        integrity = _load_json_object(
            run_dir / "stats_integrity_report.json",
            description="statistics integrity report",
        )
        run_id = _coerce_run_id(integrity.get("run_id"))
    return resolved_ticker, resolved_date, run_id


def _read_first_record_identity(run_dir: Path) -> tuple[str | None, str | None, str | None]:
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
                    f"Malformed JSONL record while inferring daily metadata at {path}: {exc}"
                ) from exc
            if not isinstance(row, dict):
                raise StatisticsInputError(
                    f"JSONL record while inferring daily metadata must be an object: {path}"
                )
            return (
                _optional_string(row.get("run_id")),
                _optional_string(row.get("symbol")),
                _optional_string(row.get("replay_date")),
            )
    return None, None, None


def _render_invalid_report(payload: dict[str, Any]) -> str:
    integrity = payload["integrity"]
    lines = [
        "# Daily Report",
        "",
        f"- Run ID: `{payload.get('run_id') or 'unknown'}`",
        "- Integrity Status: `INVALID`",
        "",
        "## Integrity",
        "",
        "Statistics artifacts failed integrity validation. Performance metrics are omitted.",
        "",
        "### Errors",
        "",
    ]
    errors = integrity.get("errors") or []
    if errors:
        lines.extend(f"- {error}" for error in errors)
    else:
        lines.append("- Unknown integrity failure")
    lines.append("")
    return "\n".join(lines)


def _render_valid_report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Daily Report",
        "",
        f"- Run ID: `{payload.get('run_id') or 'unknown'}`",
        "- Integrity Status: `VALID`",
        "",
        "## Summary",
        "",
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
        "## By Setup",
        "",
    ]
    lines.extend(_render_group(payload["by_setup"]))
    lines.extend(
        [
            "",
            "## By Direction",
            "",
        ]
    )
    lines.extend(_render_group(payload["by_direction"]))
    lines.extend(
        [
            "",
            "## By Grade",
            "",
        ]
    )
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
    plan_id = trade.get("plan_id", "unknown")
    realized_r = _format_scalar(trade.get("realized_r"))
    outcome_status = trade.get("outcome_status", "unknown")
    return f"{plan_id} ({outcome_status}, realized_r={realized_r})"


def _format_scalar(value: Any) -> str:
    if value is None:
        return "n/a"
    return str(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_optional_copy(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(path, payload)


def _write_optional_text(path: Path | None, text: str) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _coerce_run_id(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise StatisticsInputError("Statistics integrity report must include non-empty 'run_id'")
    return value


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise StatisticsInputError(f"Expected string metadata field, got {value!r}")
    if not value:
        return None
    return value
