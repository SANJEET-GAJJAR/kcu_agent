"""Milestone 1 dry-run pipeline for one trading day.

Usage:
    python scripts/run_milestone1_dry_run.py

Runs the full KCU pipeline in sequence:
  1.  PolicyReplay     — dual-timeframe cursor (2m pre-10:00, 5m from 10:00 ET)
  2.  Feature extraction
  3.  Candidate detection
  4.  Setup confirmation
  5.  Scenario watch logging
  6.  Trade plan construction
  7.  Outcome simulation + day runner persistence
  8.  Statistics
  9.  Daily report
  10. Review queue
  11. Review export

No new features. No Phase 8. Architecture unchanged.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

# ── project root on sys.path ──────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parents[1]))

from src.collector.timeframe_policy import load_timeframe_policy
from src.detectors.confirmation_engine import ConfirmationEngine
from src.detectors.detector_engine import DetectorEngine
from src.detectors.scenario_watch import ScenarioWatchResult, ScenarioWatchEngine
from src.engine.policy_replay import PolicyReplay
from src.features.extractor import FeatureExtractor
from src.features.level_context import LevelExtractor
from src.review.export import build_human_review_export
from src.review.queue import build_daily_review_queue
from src.simulator.day_runner import DayRunner
from src.simulator.plan_builder import PlanBuilder, PlanConfig
from src.statistics import build_daily_report, build_statistics

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(name)s: %(message)s",
)

# ── constants ──────────────────────────────────────────────────────────────────

TICKER = "TSLA"
DATE = "2026-06-22"
CANDLE_DIR = Path("outputs/candles")
OUTPUT_ROOT = Path("outputs/trades") / TICKER
RUN_ID = f"{DATE}_dry_run"

PATH_2M = CANDLE_DIR / f"{TICKER}_{DATE}_2m.jsonl"
PATH_5M = CANDLE_DIR / f"{TICKER}_{DATE}_5m.jsonl"

# FAILED_LTP is the only deferred-confirmation setup type that can produce valid
# trade plans in Phase 5A (LTP/Rejection/Reversal/Bounce are immediately rejected
# because level context is unavailable from candle features alone).
PLAN_CONFIG = PlanConfig(
    tradable_setup_types=frozenset({"FAILED_LTP"}),
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _banner(step: int, label: str) -> None:
    print(f"\n[Step {step}] {label}")
    print("─" * 60)


def _ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def _info(msg: str) -> None:
    print(f"    {msg}")


def _build_detector_labels_per_candle(
    feature_records,
    candidate_events,
) -> list[list[str]]:
    labels_by_index: dict[int, set[str]] = {
        record.candle_index: set() for record in feature_records
    }
    for event in candidate_events:
        labels_by_index.setdefault(event.candle_index, set()).add(event.candidate_type)
    return [
        sorted(labels_by_index.get(record.candle_index, set()))
        for record in feature_records
    ]


def _write_scenario_artifacts(
    *,
    feature_records,
    replay_records,
    candidate_events,
    run_dir: Path,
) -> ScenarioWatchResult:
    if len(replay_records) != len(feature_records):
        raise ValueError(
            "replay_records and feature_records must have equal length, got "
            f"{len(replay_records)} vs {len(feature_records)}"
        )

    detector_labels_per_candle = _build_detector_labels_per_candle(
        feature_records,
        candidate_events,
    )
    raw_indicators_per_candle = [list(record.raw_indicators) for record in replay_records]
    level_records = LevelExtractor().run(feature_records)
    result = ScenarioWatchEngine().run_and_write(
        feature_records,
        level_records,
        detector_labels_per_candle,
        output_path=run_dir / "scenario_events.jsonl",
        raw_indicators_per_candle=raw_indicators_per_candle,
    )
    _update_day_runner_summary_with_scenarios(
        run_dir / "day_runner_summary.json",
        scenario_count=len(result.events),
        scenario_events_path=result.artifacts.scenario_events_path if result.artifacts is not None else None,
    )
    return result


def _update_day_runner_summary_with_scenarios(
    summary_path: Path,
    *,
    scenario_count: int,
    scenario_events_path: Path | None,
) -> None:
    summary: dict[str, object] = {}
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["scenario_count"] = scenario_count
    if scenario_events_path is not None:
        summary["scenario_events_path"] = str(scenario_events_path)
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


# ── pipeline ──────────────────────────────────────────────────────────────────

def run() -> None:
    policy = load_timeframe_policy()
    results: dict = {}

    # ------------------------------------------------------------------
    # Step 1: PolicyReplay
    # ------------------------------------------------------------------
    _banner(1, "PolicyReplay — dual-timeframe cursor")
    replay = PolicyReplay.from_validated_paths(PATH_2M, PATH_5M, DATE, policy)

    candles_2m = sum(1 for c in replay._candles if c.snapshot.timeframe == "2")
    candles_5m = sum(1 for c in replay._candles if c.snapshot.timeframe == "5")
    total_candles = replay.total_candles

    _ok(f"Loaded {total_candles} merged candles")
    _info(f"2m (pre-10:00 ET): {candles_2m}")
    _info(f"5m (10:00-16:00 ET): {candles_5m}")

    results["candles_2m"] = candles_2m
    results["candles_5m"] = candles_5m
    results["total_replay_steps"] = total_candles

    # ------------------------------------------------------------------
    # Step 2: Feature extraction
    # ------------------------------------------------------------------
    _banner(2, "Feature extraction")
    feature_records = FeatureExtractor(replay).run()
    _ok(f"{len(feature_records)} FeatureRecords extracted")
    results["feature_records"] = len(feature_records)
    replay_records = list(replay._candles)

    # ------------------------------------------------------------------
    # Steps 3+4: Candidate detection + Setup confirmation (interleaved per candle)
    # ------------------------------------------------------------------
    _banner(3, "Candidate detection")
    _banner(4, "Setup confirmation")

    detector_engine = DetectorEngine.default()
    confirmation_engine = ConfirmationEngine()

    all_candidates = []
    all_confirmations = []

    for fr in feature_records:
        candidates = detector_engine.process(fr)
        all_candidates.extend(candidates)
        confirmations = confirmation_engine.step(candidates, fr)
        all_confirmations.extend(confirmations)

    # Flush any deferred candidates still pending at end of session
    if feature_records:
        final = confirmation_engine.flush(feature_records[-1])
        all_confirmations.extend(final)

    # Tally by type
    candidate_by_type: dict[str, int] = {}
    for ev in all_candidates:
        candidate_by_type[ev.candidate_type] = candidate_by_type.get(ev.candidate_type, 0) + 1

    def _outcome_str(e) -> str:
        return e.outcome.name if hasattr(e.outcome, "name") else str(e.outcome)

    confirm_confirmed = [e for e in all_confirmations if _outcome_str(e) == "CONFIRMED_SETUP"]
    confirm_rejected  = [e for e in all_confirmations if _outcome_str(e) == "REJECTED_SETUP"]

    _ok(f"{len(all_candidates)} candidates detected")
    for ctype, count in sorted(candidate_by_type.items()):
        _info(f"{ctype}: {count}")

    _ok(f"{len(all_confirmations)} confirmation events")
    _info(f"CONFIRMED_SETUP: {len(confirm_confirmed)}")
    _info(f"REJECTED_SETUP:  {len(confirm_rejected)}")

    results["candidates_total"] = len(all_candidates)
    results["candidates_by_type"] = candidate_by_type
    results["confirmed_setups"] = len(confirm_confirmed)
    results["rejected_setups"] = len(confirm_rejected)

    # ------------------------------------------------------------------
    # Step 5: Scenario watch logging
    # ------------------------------------------------------------------
    _banner(5, "Scenario watch logging")

    # Scenario watches are informational only. They never create plans and do
    # not affect confirmation, simulation, or statistics semantics.
    provisional_run_dir = OUTPUT_ROOT / RUN_ID
    provisional_run_dir.mkdir(parents=True, exist_ok=True)
    scenario_result = _write_scenario_artifacts(
        feature_records=feature_records,
        replay_records=replay_records,
        candidate_events=all_candidates,
        run_dir=provisional_run_dir,
    )
    _ok(f"{len(scenario_result.events)} scenario watch events")
    if scenario_result.artifacts is not None:
        _info(f"scenario_events: {scenario_result.artifacts.scenario_events_path}")
    results["scenario_count"] = len(scenario_result.events)
    results["scenario_events_path"] = (
        str(scenario_result.artifacts.scenario_events_path)
        if scenario_result.artifacts is not None else None
    )

    # ------------------------------------------------------------------
    # Steps 6+7: Trade plans + Outcome simulation + Day runner persistence
    # ------------------------------------------------------------------
    _banner(6, "Trade plan construction + Outcome simulation + Day runner persistence")

    # Factory that always returns a freshly-built PolicyReplay at cursor=0.
    # PolicyReplay._build re-indexes candle_index on each call so
    # OutcomeSimulator's cursor arithmetic stays correct across the merged sequence.
    replay_factory = lambda: PolicyReplay.from_paths(PATH_2M, PATH_5M, DATE, policy)

    runner = DayRunner(plan_builder=PlanBuilder(PLAN_CONFIG))
    day_run = runner.run_from_confirmations(
        confirmations=all_confirmations,
        feature_records=feature_records,
        replay_factory=replay_factory,
        output_root=OUTPUT_ROOT,
        run_id=RUN_ID,
    )

    _ok(f"{len(day_run.valid_plans)} valid trade plans")
    _ok(f"{len(day_run.rejected_plans)} rejected trade plans")
    _ok(f"{len(day_run.outcomes)} outcomes simulated")

    if day_run.outcomes:
        from src.simulator.execution_contract import ExecutionOutcome
        outcome_counts: dict[str, int] = {}
        for o in day_run.outcomes:
            label = o.outcome_status.name if hasattr(o.outcome_status, "name") else str(o.outcome_status)
            outcome_counts[label] = outcome_counts.get(label, 0) + 1
        for label, count in sorted(outcome_counts.items()):
            _info(f"{label}: {count}")

    results["valid_trade_plans"] = len(day_run.valid_plans)
    results["rejected_trade_plans"] = len(day_run.rejected_plans)
    results["outcomes"] = len(day_run.outcomes)

    run_dir = day_run.artifacts.output_dir
    scenario_result = _write_scenario_artifacts(
        feature_records=feature_records,
        replay_records=replay_records,
        candidate_events=all_candidates,
        run_dir=run_dir,
    )
    results["scenario_count"] = len(scenario_result.events)
    results["scenario_events_path"] = (
        str(scenario_result.artifacts.scenario_events_path)
        if scenario_result.artifacts is not None else None
    )

    # ------------------------------------------------------------------
    # Step 8: Statistics
    # ------------------------------------------------------------------
    _banner(8, "Statistics")
    stats_result = build_statistics(run_dir)
    summary = stats_result.summary
    _ok(f"Integrity: {'PASSED' if stats_result.integrity_report.passed else 'FAILED'}")
    _info(f"valid plans:    {summary.get('valid_trade_plan_count', 0)}")
    _info(f"simulated:      {summary.get('simulated_trade_plan_count', 0)}")
    _info(f"wins:           {summary.get('wins', 0)}")
    _info(f"losses:         {summary.get('losses', 0)}")
    _info(f"ambiguous:      {summary.get('ambiguous', 0)}")
    _info(f"unresolved:     {summary.get('unresolved', 0)}")
    _info(f"win rate:       {summary.get('win_rate')}")
    _info(f"avg R:          {summary.get('avg_realized_r')}")
    _info(f"total R:        {summary.get('total_realized_r')}")
    results["stats_summary"] = summary

    # ------------------------------------------------------------------
    # Step 9: Daily report
    # ------------------------------------------------------------------
    _banner(9, "Daily report")
    report_result = build_daily_report(
        run_dir,
        ticker=TICKER,
        trade_date=DATE,
    )
    _ok(f"Status: {report_result.payload.get('report_status')}")
    report_paths = {
        "daily_report_md":   str(report_result.artifacts.daily_report_md_path),
        "daily_report_json": str(report_result.artifacts.daily_report_json_path),
    }
    for k, v in report_paths.items():
        _info(f"{k}: {v}")
    results["report_paths"] = report_paths

    # ------------------------------------------------------------------
    # Step 10: Review queue
    # ------------------------------------------------------------------
    _banner(10, "Review queue")
    review_queue_result = build_daily_review_queue(
        run_dir,
        ticker=TICKER,
        trade_date=DATE,
    )
    _ok(f"{len(review_queue_result.entries)} review queue entries")
    _info(f"queue: {review_queue_result.artifacts.review_queue_path}")
    results["review_queue_entries"] = len(review_queue_result.entries)
    results["review_paths"] = {
        "queue": str(review_queue_result.artifacts.review_queue_path),
        "summary": str(review_queue_result.artifacts.review_summary_path),
    }

    # ------------------------------------------------------------------
    # Step 11: Review export
    # ------------------------------------------------------------------
    _banner(11, "Review export")
    export_result = build_human_review_export(run_dir)
    _ok("Review dashboard and item exports written")
    _info(f"dashboard_md:   {export_result.artifacts.review_dashboard_md_path}")
    _info(f"dashboard_json: {export_result.artifacts.review_dashboard_json_path}")
    _info(f"items_md:       {export_result.artifacts.review_items_md_path}")
    _info(f"items_json:     {export_result.artifacts.review_items_json_path}")
    results["review_paths"].update({
        "dashboard_md":   str(export_result.artifacts.review_dashboard_md_path),
        "dashboard_json": str(export_result.artifacts.review_dashboard_json_path),
        "items_md":       str(export_result.artifacts.review_items_md_path),
        "items_json":     str(export_result.artifacts.review_items_json_path),
    })

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "═" * 60)
    print("MILESTONE 1 DRY RUN — COMPLETE")
    print("═" * 60)
    print(f"  Ticker:              {TICKER}")
    print(f"  Date:                {DATE}")
    print(f"  Run ID:              {RUN_ID}")
    print(f"  Output dir:          {run_dir}")
    print()
    print(f"  Candles (2m):        {results['candles_2m']}")
    print(f"  Candles (5m):        {results['candles_5m']}")
    print(f"  Total replay steps:  {results['total_replay_steps']}")
    print()
    print(f"  Candidates:          {results['candidates_total']}")
    print(f"  Confirmed setups:    {results['confirmed_setups']}")
    print(f"  Scenario watches:    {results['scenario_count']}")
    print()
    print(f"  Valid trade plans:   {results['valid_trade_plans']}")
    print(f"  Rejected plans:      {results['rejected_trade_plans']}")
    print(f"  Outcomes simulated:  {results['outcomes']}")
    print()
    print(f"  Wins:                {summary.get('wins', 0)}")
    print(f"  Losses:              {summary.get('losses', 0)}")
    print(f"  Win rate:            {summary.get('win_rate')}")
    print(f"  Total R:             {summary.get('total_realized_r')}")
    print()
    print(f"  Daily report (MD):   {report_paths['daily_report_md']}")
    print(f"  Daily report (JSON): {report_paths['daily_report_json']}")
    if results.get("scenario_events_path"):
        print(f"  Scenario events:     {results['scenario_events_path']}")
    print()

    return results


if __name__ == "__main__":
    run()
