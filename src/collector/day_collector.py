"""Day collector — collect one complete trading day to JSONL.

Public API:
    result = await collect_day(
        ticker="TSLA",
        date="2024-01-15",
        timeframe="2",
        output_dir=Path("outputs/candles"),
        session_end_et="16:00",
    )

Rules:
  - Generic: no ticker-specific or KCU-specific code.
  - Deterministic: same inputs always produce the same JSONL.
  - Replay-safe: no lookahead. Each candle is read after it closes.
  - Resume-safe: if interrupted, re-run resumes from last written candle.
  - Append-only: JSONL is never truncated, only appended.
  - Idempotent: running twice on a completed day produces identical output.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .candle_record import CandleRecord, build_record
from .candle_schema import CandleSnapshot
from .chart_preflight import (
    ChartPreflightConfig,
    ChartPreflight,
    PreflightResult,
    write_preflight_companion,
)
from .jsonl_store import JsonlStore, validate_jsonl
from .workspace_preflight import (
    WorkspaceConfig,
    WorkspacePreflight,
    WorkspacePreflightError,
    WorkspacePreflightResult,
    load_workspace_config,
)


class ProductionPreflightRequiredError(Exception):
    """Raised when collect_day() is called without preflight_config in production mode.

    Production runs (dry_run=False, which is the default) must always provide a
    ChartPreflightConfig to ensure candles are collected under the correct
    TradingView chart environment.

    To bypass in unit tests or explicitly marked dry runs:
        collect_day(..., dry_run=True)
    """


class IndicatorQualityError(Exception):
    """Raised when collected candles are missing required indicator payload.

    Triggered by build_indicator_quality_report() when:
    - raw_indicators is empty on one or more candles (no studies captured)
    - KCU indicator study is absent or has an empty values dict
    - Volume is zero for the majority of bars

    Fix: confirm the required indicators are visible on the TradingView chart,
    re-enter replay mode, and re-collect.
    """


class DegenerateOHLCError(Exception):
    """Raised when collected candles have open=high=low=close above the allowed threshold.

    This indicates the TradingView replay returned close-only (tick) data instead of
    full OHLCV candles.  Real bars may legitimately be doji (O=H=L=C) on low-volume
    symbols, but if more than DEGENERATE_OHLC_THRESHOLD of bars are degenerate, the
    collection is invalid.

    Fix: restart the MCP server, re-enter replay mode, and re-collect.  If the problem
    persists across sessions, run scripts/debug_ohlcv_replay.py during a live replay
    session to identify the root cause.
    """


# Maximum fraction of bars allowed to have open=high=low=close before failing.
# A genuine doji is valid but > 5% degenerate across a full session means bad data.
DEGENERATE_OHLC_THRESHOLD = 0.05
from .replay_controller import ReplayController, ReplayControllerError
from .session_clock import (
    MARKET_CLOSE_ET,
    expected_candle_count,
    is_past_session_end,
    session_end_timestamp,
)
from .tv_client import TradingViewClient, TVClientError

log = logging.getLogger(__name__)

# Number of consecutive identical timestamps before declaring end-of-available-data.
_STUCK_THRESHOLD = 3

# Bars may not populate immediately after replay_start. These constants control
# the readiness poll inside _wait_for_chart_ready.
_CHART_READY_MAX_ATTEMPTS = 10
_CHART_READY_DELAY = 1.5  # seconds between poll attempts

# Timeframe string normalisation map (e.g. "2m" → "2")
_TIMEFRAME_ALIASES = {
    "1m": "1", "2m": "2", "3m": "3", "5m": "5",
    "10m": "10", "15m": "15", "30m": "30", "60m": "60", "1h": "60",
}


@dataclass
class CollectionResult:
    ticker: str
    date: str
    timeframe: str
    output_path: Path
    candles_written: int
    candles_skipped: int      # duplicates skipped (resume)
    complete: bool             # True if session end was reached
    stop_reason: str           # "session_end" | "end_of_data" | "error"
    validation_errors: list[str]
    preflight_metadata: dict | None = None    # None when preflight_config not provided
    workspace_metadata: dict | None = None    # None when workspace_config not provided


async def collect_day(
    ticker: str,
    date: str,
    timeframe: str,
    output_dir: Path = Path("outputs/candles"),
    session_end_et: str = MARKET_CLOSE_ET,
    include_indicators: bool = True,
    preflight_config: ChartPreflightConfig | None = None,
    workspace_config: WorkspaceConfig | None = None,
    dry_run: bool = False,
) -> CollectionResult:
    """Collect one complete trading day from TradingView replay to JSONL.

    Args:
        ticker:             Symbol, e.g. "TSLA". Generic — any TradingView ticker.
        date:               ISO date, e.g. "2024-01-15".
        timeframe:          Chart timeframe, e.g. "2" or "2m" (both accepted).
        output_dir:         Directory to write JSONL files into.
        session_end_et:     Stop collecting at this ET time (default: "16:00").
        include_indicators: If True, read data_get_study_values per candle.
        preflight_config:   Required in production mode (dry_run=False).
                            Collection aborts if preflight fails (PreflightFailedError).
        workspace_config:   When provided, verifies the active TradingView layout is the
                            dedicated backtesting workspace before any chart actions.
                            Raises WorkspacePreflightError if the live workspace is
                            detected or detection fails and override is disabled.
        dry_run:            If True, skip preflight enforcement (for unit tests only).
                            Must be False for all real collection runs.

    Raises:
        ProductionPreflightRequiredError: If dry_run=False and preflight_config=None.
            All production collection runs must pass a ChartPreflightConfig.
        WorkspacePreflightError: If workspace_config provided and workspace check fails.

    Returns:
        CollectionResult with counts, output path, and validation summary.
    """
    if not dry_run and preflight_config is None:
        raise ProductionPreflightRequiredError(
            "collect_day() requires preflight_config in production mode (dry_run=False). "
            "Provide a ChartPreflightConfig via load_preflight_config() or pass "
            "dry_run=True explicitly for unit tests."
        )

    ticker = ticker.upper().strip()
    timeframe = _normalise_timeframe(timeframe)
    output_dir = Path(output_dir)

    output_path = _output_path(ticker, date, timeframe, output_dir)
    session_end_ts = session_end_timestamp(date, session_end_et)
    est_count = expected_candle_count(date, timeframe, end_time_et=session_end_et)

    log.info(
        "Collecting %s %s @ %sm → %s (est. %d candles, session end ET %s)",
        ticker, date, timeframe, output_path, est_count, session_end_et,
    )

    # Fast-path: already complete
    if _is_already_complete(output_path, session_end_ts):
        log.info("Output already complete — skipping collection")
        vr = validate_jsonl(output_path)
        store = JsonlStore(output_path)
        return CollectionResult(
            ticker=ticker, date=date, timeframe=timeframe,
            output_path=output_path,
            candles_written=0, candles_skipped=store.record_count,
            complete=True, stop_reason="already_complete",
            validation_errors=vr.errors,
        )

    preflight_result: PreflightResult | None = None
    workspace_result: WorkspacePreflightResult | None = None

    async with TradingViewClient() as client:
        # --- Workspace preflight (must run before any destructive chart action) ---
        if workspace_config is not None:
            workspace_pf = WorkspacePreflight(workspace_config)
            workspace_result = await workspace_pf.run(client)
            # run() raises WorkspacePreflightError if live workspace detected or unknown
            # workspace detected and allow_unknown_workspace_for_collection=False.

        # --- Chart preflight check (when configured) ---
        if preflight_config is not None:
            preflight = ChartPreflight(preflight_config)
            preflight_result = await preflight.run(client, output_dir)
            # run() raises PreflightFailedError on failure — collection aborts

        ctrl = ReplayController(client)
        await ctrl.load_ticker(ticker)      # first destructive action — workspace gate above
        await ctrl.set_timeframe(timeframe)
        await ctrl.load_trading_day(date)
        await _wait_for_chart_ready(ctrl)

        result = await _run_collection_loop(
            ctrl=ctrl,
            output_path=output_path,
            session_end_ts=session_end_ts,
            ticker=ticker,
            date=date,
            timeframe=timeframe,
            include_indicators=include_indicators,
            est_count=est_count,
        )

        try:
            await ctrl.stop_replay()
        except Exception:
            pass  # Best-effort cleanup

    vr = validate_jsonl(output_path)
    result.validation_errors = vr.errors

    if workspace_result is not None:
        result.workspace_metadata = workspace_result.to_metadata()

    if preflight_result is not None:
        result.preflight_metadata = preflight_result.to_metadata()
        write_preflight_companion(preflight_result, output_path)

    if vr.errors:
        log.warning("Validation found %d error(s): %s", len(vr.errors), vr.errors)
    else:
        log.info(
            "Collection complete: %d candles written, %d skipped, valid=%s",
            result.candles_written, result.candles_skipped, vr.valid,
        )

    # Quality gates — run only when there is data to check
    if result.candles_written > 0 or result.candles_skipped > 0:
        build_ohlc_quality_report(
            output_path,
            ticker=ticker,
            date=date,
            timeframe=timeframe,
        )
        if include_indicators:
            build_indicator_quality_report(
                output_path,
                ticker=ticker,
                date=date,
                timeframe=timeframe,
            )

    return result


async def _run_collection_loop(
    ctrl: ReplayController,
    output_path: Path,
    session_end_ts: int,
    ticker: str,
    date: str,
    timeframe: str,
    include_indicators: bool,
    est_count: int,
) -> CollectionResult:
    """Inner collection loop. Handles resume, stuck detection, session boundary."""
    candles_written = 0
    candles_skipped = 0
    stop_reason = "error"
    prev_ts: int | None = None
    stuck_count = 0
    # Bars before midnight UTC of the replay date belong to the previous session.
    # replay_start positions the cursor BEFORE bar 0, so the first one or two
    # reads may return bars from that prior session. Skip them silently.
    day_start_utc = int(datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())

    with JsonlStore(output_path) as store:
        seen_timestamps = set(store.seen_timestamps)
        candle_index = store.record_count

        while True:
            # --- Read current candle ---
            try:
                snapshot = await ctrl.read_current_candle()
            except ReplayControllerError as exc:
                log.error("Failed to read candle: %s", exc)
                stop_reason = "error"
                break

            ts = snapshot.timestamp

            # --- Skip pre-replay bars from previous session ---
            if ts < day_start_utc:
                log.debug("Skipping pre-replay bar ts=%d (before %s midnight UTC=%d)", ts, date, day_start_utc)
                try:
                    await ctrl.advance_one_candle()
                except Exception:
                    pass
                continue

            # --- Stuck detection ---
            if ts == prev_ts:
                stuck_count += 1
                log.debug("Same timestamp %d (%d/%d)", ts, stuck_count, _STUCK_THRESHOLD)
                if stuck_count >= _STUCK_THRESHOLD:
                    log.info("Replay not advancing — end of available data at ts=%d", ts)
                    stop_reason = "end_of_data"
                    break
                # Don't write; try advancing again
                await ctrl.advance_one_candle()
                continue

            stuck_count = 0
            prev_ts = ts

            # --- Write candle if not already seen ---
            if ts in seen_timestamps:
                candles_skipped += 1
                log.debug("Resuming: skipping already-written ts=%d", ts)
            else:
                indicators: dict[str, Any] = {}
                raw_indicators: list[dict] = []
                if include_indicators:
                    try:
                        raw = await ctrl.read_indicator_values()
                        indicators = _flatten_indicators(raw)
                        raw_indicators = _extract_raw_studies(raw)
                    except Exception as exc:
                        log.warning("Could not read indicators at ts=%d: %s", ts, exc)

                record = build_record(snapshot, indicators, candle_index, raw_indicators)
                if store.append(record):
                    seen_timestamps.add(ts)
                    candle_index += 1
                    candles_written += 1

                    if candles_written % 50 == 0:
                        log.info(
                            "Progress: %d/%d candles (ts=%d)",
                            candles_written + candles_skipped, est_count, ts,
                        )

            # --- Session boundary ---
            if is_past_session_end(ts, session_end_ts):
                log.info("Session end reached at ts=%d (>= %d)", ts, session_end_ts)
                stop_reason = "session_end"
                break

            # --- Advance ---
            try:
                await ctrl.advance_one_candle()
            except Exception as exc:
                log.error("replay_step failed: %s", exc)
                stop_reason = "error"
                break

    return CollectionResult(
        ticker=ticker, date=date, timeframe=timeframe,
        output_path=output_path,
        candles_written=candles_written,
        candles_skipped=candles_skipped,
        complete=(stop_reason in ("session_end", "already_complete")),
        stop_reason=stop_reason,
        validation_errors=[],  # filled in by caller
    )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _output_path(ticker: str, date: str, timeframe: str, output_dir: Path) -> Path:
    return output_dir / f"{ticker}_{date}_{timeframe}m.jsonl"


def _quality_report_path(output_path: Path) -> Path:
    """Return the sibling quality report path for a given JSONL output file."""
    return output_path.with_name(output_path.stem + "_quality.json")


def build_ohlc_quality_report(
    output_path: Path,
    ticker: str,
    date: str,
    timeframe: str,
    *,
    threshold: float = DEGENERATE_OHLC_THRESHOLD,
    write: bool = True,
) -> dict:
    """Scan the JSONL file for degenerate OHLC bars (open=high=low=close).

    Returns a dict with quality metrics.  If write=True, also writes
    ``{stem}_quality.json`` next to the JSONL file.

    Raises DegenerateOHLCError if the degenerate fraction exceeds threshold.
    """
    store = JsonlStore(output_path)
    records = store.read_all()

    total = len(records)
    degenerate = sum(
        1 for r in records
        if r.snapshot.open == r.snapshot.high == r.snapshot.low == r.snapshot.close
    )
    zero_volume = sum(1 for r in records if r.snapshot.volume == 0)
    frac = degenerate / total if total > 0 else 0.0

    generated_at = datetime.now(timezone.utc).isoformat()
    passed = frac <= threshold
    report = {
        "ticker": ticker,
        "date": date,
        "timeframe": timeframe,
        "generated_at": generated_at,
        "total_bars": total,
        "degenerate_bars": degenerate,
        "degenerate_fraction": round(frac, 4),
        "threshold": threshold,
        "zero_volume_bars": zero_volume,
        "quality_passed": passed,
        "diagnosis": (
            "PASSED: OHLC spread looks real."
            if passed else
            f"FAILED: {degenerate}/{total} bars ({frac:.1%}) have open=high=low=close. "
            "This indicates TradingView replay returned close-only (tick) data instead of "
            "full OHLCV candles. "
            "Run scripts/debug_ohlcv_replay.py during a live replay session to diagnose. "
            "Fix the MCP OHLCV source and re-collect before running the pipeline."
        ),
    }

    if write:
        report_path = _quality_report_path(output_path)
        report_path.write_text(json.dumps(report, indent=2))
        log.info(
            "OHLC quality report written: %s (degenerate=%.1f%%, passed=%s)",
            report_path, frac * 100, passed,
        )

    if not passed:
        raise DegenerateOHLCError(
            f"{ticker} {date} {timeframe}m: {degenerate}/{total} bars ({frac:.1%}) "
            f"have open=high=low=close — exceeds threshold {threshold:.0%}. "
            "Collection rejected. See quality report and debug_ohlcv_replay.py."
        )

    return report


# Substring patterns that must appear in at least one study name per candle.
# Case-insensitive.  The KCU indicator is required; all others are optional.
_REQUIRED_STUDY_SUBSTRINGS = ("KCU",)
_OPTIONAL_STUDY_SUBSTRINGS = ("EMA", "SMA", "VWAP", "Stop Loss", "Volume")


def _indicator_quality_report_path(output_path: Path) -> Path:
    return output_path.with_name(output_path.stem + "_indicator_quality.json")


def build_indicator_quality_report(
    output_path: Path,
    ticker: str,
    date: str,
    timeframe: str,
    *,
    write: bool = True,
) -> dict:
    """Scan the JSONL file for indicator completeness and KCU study presence.

    Checks per-candle:
    - raw_indicators is non-empty (at least one study captured)
    - at least one study has "KCU" in its name (case-insensitive)
    - that KCU study has a non-empty values dict
    - volume > 0 (from snapshot)

    Optional indicators (EMA, SMA, VWAP, Stop Loss Widget) are noted but do
    not cause failure.  Unknown additional studies are always allowed.

    Raises IndicatorQualityError if required indicators are absent.

    Note on candle-specificity:
        data_get_study_values reads from TradingView's Data Window, which
        reflects the bar at the CURRENT replay position.  Values are assumed
        to be candle-specific because the collector calls read_indicator_values
        immediately after each replay step.  This is unverified for all
        timeframes — run scripts/debug_ohlcv_replay.py to confirm with a live
        replay session before relying on multi-candle indicator trends.
    """
    store = JsonlStore(output_path)
    records = store.read_all()
    total = len(records)

    # 9:30 AM ET — KCU indicator only provides values from session open onwards.
    # Pre-market bars (before 9:30) will not have KCU loaded; exclude them from
    # the KCU presence check to avoid false-positive failures.
    y, m, d_num = (int(x) for x in date.split("-"))
    et_offset = -4 if 4 <= m <= 10 else -5   # EDT Apr-Oct, EST Nov-Mar
    from datetime import timedelta
    _session_open = datetime(
        y, m, d_num, 9, 30, 0,
        tzinfo=timezone(timedelta(hours=et_offset)),
    )
    session_start_ts = int(_session_open.timestamp())

    missing_raw = 0          # candles with raw_indicators == []
    missing_kcu = 0          # session candles without any KCU study
    empty_kcu_values = 0     # candles where KCU study exists but has no values
    zero_volume = 0          # candles with snapshot.volume == 0

    optional_presence: dict[str, int] = {s: 0 for s in _OPTIONAL_STUDY_SUBSTRINGS}

    for r in records:
        studies = r.raw_indicators
        if not studies:
            missing_raw += 1
            if r.snapshot.timestamp >= session_start_ts:
                missing_kcu += 1
            continue

        study_names_lower = [s.get("name", "").lower() for s in studies]

        # KCU check — only required for session bars (9:30+ ET).
        # Pre-market bars are excluded because the indicator loads after open.
        if r.snapshot.timestamp >= session_start_ts:
            kcu_studies = [
                s for s in studies
                if "kcu" in s.get("name", "").lower()
            ]
            if not kcu_studies:
                missing_kcu += 1
            else:
                for kcu in kcu_studies:
                    if not kcu.get("values"):
                        empty_kcu_values += 1
                        break

        # Optional indicator presence
        for sub in _OPTIONAL_STUDY_SUBSTRINGS:
            if any(sub.lower() in n for n in study_names_lower):
                optional_presence[sub] += 1

        if r.snapshot.volume == 0:
            zero_volume += 1

    required_failures = []
    if missing_raw > 0:
        required_failures.append(
            f"{missing_raw}/{total} candles have empty raw_indicators (no studies captured)"
        )
    if missing_kcu > 0:
        required_failures.append(
            f"{missing_kcu}/{total} candles missing a KCU study"
        )
    if empty_kcu_values > 0:
        required_failures.append(
            f"{empty_kcu_values}/{total} candles have KCU study with empty values"
        )

    passed = len(required_failures) == 0
    generated_at = datetime.now(timezone.utc).isoformat()

    report = {
        "ticker": ticker,
        "date": date,
        "timeframe": timeframe,
        "generated_at": generated_at,
        "total_bars": total,
        "candle_specificity_note": (
            "Indicator values are read from TradingView's Data Window at the current "
            "replay position immediately after each replay step. They are assumed "
            "candle-specific. Verify with scripts/debug_ohlcv_replay.py during a "
            "live replay session before relying on multi-candle indicator trends."
        ),
        "required_checks": {
            "raw_indicators_present": missing_raw == 0,
            "kcu_study_present": missing_kcu == 0,
            "kcu_values_non_empty": empty_kcu_values == 0,
        },
        "optional_checks": {
            sub: {"bars_present": cnt, "bars_total": total}
            for sub, cnt in optional_presence.items()
        },
        "zero_volume_bars": zero_volume,
        "missing_raw_indicators": missing_raw,
        "missing_kcu_study": missing_kcu,
        "empty_kcu_values": empty_kcu_values,
        "quality_passed": passed,
        "failures": required_failures,
        "diagnosis": (
            "PASSED: Required indicator payload present on all candles."
            if passed else
            "FAILED: " + "; ".join(required_failures) + ". "
            "Ensure KCU indicator is visible on the chart before re-collecting."
        ),
    }

    if write:
        report_path = _indicator_quality_report_path(output_path)
        report_path.write_text(json.dumps(report, indent=2))
        log.info(
            "Indicator quality report written: %s (passed=%s, missing_kcu=%d)",
            report_path, passed, missing_kcu,
        )

    if not passed:
        raise IndicatorQualityError(
            f"{ticker} {date} {timeframe}m indicator quality failed: "
            + "; ".join(required_failures)
        )

    return report


def _normalise_timeframe(tf: str) -> str:
    """Accept "2m", "2", "5m", "5", etc. Return canonical form like "2"."""
    normalised = _TIMEFRAME_ALIASES.get(tf.lower(), tf)
    return normalised


async def _wait_for_chart_ready(ctrl: ReplayController) -> None:
    """Poll until TradingView chart bars are available after replay_start.

    replay_start can take 1-3 s to populate bar data.  The first read may
    return a bar from the prior session (before midnight UTC of the replay
    date), which the collection loop's pre-replay filter will discard.  This
    function simply ensures at least one successful read before the loop
    starts so the loop doesn't crash on a bare "chart still loading" error.
    """
    for attempt in range(1, _CHART_READY_MAX_ATTEMPTS + 1):
        try:
            await ctrl.read_current_candle()
            log.debug("Chart ready (attempt %d)", attempt)
            return
        except (TVClientError, ReplayControllerError) as exc:
            msg = str(exc).lower()
            if "loading" in msg or "extract" in msg or "bars" in msg:
                if attempt < _CHART_READY_MAX_ATTEMPTS:
                    log.debug(
                        "Chart still loading (attempt %d/%d), retrying in %.1fs",
                        attempt, _CHART_READY_MAX_ATTEMPTS, _CHART_READY_DELAY,
                    )
                    await asyncio.sleep(_CHART_READY_DELAY)
                else:
                    raise ReplayControllerError(
                        f"Chart did not become ready after {_CHART_READY_MAX_ATTEMPTS} attempts: {exc}"
                    ) from exc
            else:
                raise


def _is_already_complete(path: Path, session_end_ts: int) -> bool:
    """Return True if the JSONL file exists and contains a candle at/after session_end_ts."""
    if not path.exists():
        return False
    store = JsonlStore(path)
    try:
        records = store.read_all()
    except Exception:
        return False
    if not records:
        return False
    last_ts = records[-1].timestamp
    return last_ts >= session_end_ts


def _extract_raw_studies(raw: dict[str, Any]) -> list[dict]:
    """Extract the raw studies list from a data_get_study_values response.

    Returns a list of {"name": str, "values": {str: Any}} dicts preserving
    study attribution, all exposed fields/plots, and raw string values exactly
    as returned by the MCP server.  No interpretation, no type conversion.
    """
    if not isinstance(raw, dict):
        return []
    studies = raw.get("studies")
    if not isinstance(studies, list):
        return []
    result = []
    for study in studies:
        if not isinstance(study, dict):
            continue
        name = study.get("name") or study.get("title") or ""
        values = study.get("values") or {}
        if isinstance(values, dict):
            result.append({"name": name, "values": dict(values)})
    return result


def _flatten_indicators(raw: dict[str, Any]) -> dict[str, Any]:
    """Extract a flat name→value dict from data_get_study_values output.

    The MCP tool returns something like:
        {"success": True, "studies": [{"name": "RSI", "values": {"RSI": 55.2}}]}
    We flatten to: {"RSI": 55.2}

    If the structure is unexpected, return the raw dict minus "success".
    No interpretation — purely structural flattening.
    """
    if not isinstance(raw, dict):
        return {}

    studies = raw.get("studies")
    if not isinstance(studies, list):
        # Unexpected structure — store raw minus success flag
        return {k: v for k, v in raw.items() if k != "success"}

    flat: dict[str, Any] = {}
    for study in studies:
        if not isinstance(study, dict):
            continue
        name = study.get("name", "unknown")
        values = study.get("values", {})
        if isinstance(values, dict):
            for k, v in values.items():
                # Prefix with study name to avoid collisions
                flat[f"{name}.{k}" if k != name else name] = v
        else:
            flat[name] = values

    return flat
