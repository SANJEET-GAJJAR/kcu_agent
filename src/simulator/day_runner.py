"""Day-level Phase 5C runner for plan persistence and outcome simulation."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from src.detectors.confirmation_event import ConfirmationEvent
from src.engine.backtest_replay import BacktestReplay
from src.features.feature_record import FeatureRecord
from src.simulator.outcome import OutcomeResult
from src.simulator.plan_builder import PlanBuilder, PlanConfig
from src.simulator.simulator import OutcomeSimulator
from src.simulator.trade_plan import TradePlan


@dataclass(frozen=True)
class DayRunArtifacts:
    """Filesystem outputs produced by one deterministic day run."""

    run_id: str
    output_dir: Path
    trade_plans_path: Path
    rejected_trade_plans_path: Path
    trade_outcomes_path: Path
    summary_path: Path


@dataclass
class DayRunResult:
    """In-memory result plus filesystem artifacts for one day run."""

    run_id: str
    valid_plans: list[TradePlan]
    rejected_plans: list[TradePlan]
    outcomes: list[OutcomeResult]
    artifacts: DayRunArtifacts
    summary: dict[str, object]


class DayRunner:
    """Builds plans, simulates valid ones, and persists day-level outputs."""

    def __init__(
        self,
        plan_builder: PlanBuilder | None = None,
        outcome_simulator: OutcomeSimulator | None = None,
    ) -> None:
        self._plan_builder = plan_builder or PlanBuilder()
        self._outcome_simulator = outcome_simulator or OutcomeSimulator()

    def run_from_confirmations(
        self,
        confirmations: list[ConfirmationEvent],
        feature_records: list[FeatureRecord],
        *,
        replay_factory: Callable[[], BacktestReplay],
        output_root: Path | str,
        run_id: str,
    ) -> DayRunResult:
        """Build plans from confirmation events, then persist outcomes."""
        feature_by_index = _index_features(feature_records)
        ordered_confirmations = sorted(
            confirmations,
            key=lambda e: (
                e.evaluated_at_candle_index,
                e.evaluated_at_timestamp,
                e.setup_type,
                e.watch_type,
                e.candidate_candle_index,
                e.timestamp,
            ),
        )

        plans = [
            self._plan_builder.build(
                event,
                feature_by_index[event.evaluated_at_candle_index],
            )
            for event in ordered_confirmations
        ]
        return self.run_from_trade_plans(
            plans,
            replay_factory=replay_factory,
            output_root=output_root,
            run_id=run_id,
        )

    def run_from_confirmations_path(
        self,
        confirmations: list[ConfirmationEvent],
        feature_records: list[FeatureRecord],
        *,
        replay_path: Path | str,
        output_root: Path | str,
        run_id: str,
    ) -> DayRunResult:
        """Production path entrypoint: always validates collection first."""
        replay_path = Path(replay_path)
        return self.run_from_confirmations(
            confirmations,
            feature_records,
            replay_factory=lambda: BacktestReplay.from_validated_path(replay_path),
            output_root=output_root,
            run_id=run_id,
        )

    def run_from_trade_plans(
        self,
        trade_plans: list[TradePlan],
        *,
        replay_factory: Callable[[], BacktestReplay],
        output_root: Path | str,
        run_id: str,
    ) -> DayRunResult:
        """Persist valid/rejected plans and simulate outcomes for valid ones only."""
        ordered_plans = sorted(
            trade_plans,
            key=lambda p: (p.candle_index, p.timestamp, p.plan_id),
        )
        valid_plans = [p for p in ordered_plans if p.is_valid()]
        rejected_plans = [p for p in ordered_plans if not p.is_valid()]

        outcomes = [
            self._outcome_simulator.simulate(plan, replay_factory())
            for plan in valid_plans
        ]

        ordered_outcomes = sorted(
            outcomes,
            key=lambda o: (
                o.entry_candle_index,
                o.exit_candle_index if o.exit_candle_index is not None else 10**9,
                o.plan_id,
            ),
        )

        artifacts = _artifact_paths(Path(output_root), run_id)
        _write_jsonl_records(
            artifacts.trade_plans_path,
            [
                {
                    "run_id": run_id,
                    "record_type": "trade_plan",
                    **plan.to_dict(),
                }
                for plan in valid_plans
            ],
        )
        _write_jsonl_records(
            artifacts.rejected_trade_plans_path,
            [
                {
                    "run_id": run_id,
                    "record_type": "rejected_trade_plan",
                    **plan.to_dict(),
                }
                for plan in rejected_plans
            ],
        )
        _write_jsonl_records(
            artifacts.trade_outcomes_path,
            [
                {
                    "run_id": run_id,
                    "record_type": "trade_outcome",
                    **outcome.to_dict(),
                }
                for outcome in ordered_outcomes
            ],
        )

        summary = {
            "run_id": run_id,
            "valid_trade_plan_count": len(valid_plans),
            "rejected_trade_plan_count": len(rejected_plans),
            "trade_outcome_count": len(ordered_outcomes),
            "simulated_trade_plan_count": len(valid_plans),
            "skipped_trade_plan_count": len(rejected_plans),
            "trade_plan_ids": [p.plan_id for p in valid_plans],
            "rejected_trade_plan_ids": [p.plan_id for p in rejected_plans],
            "outcome_plan_ids": [o.plan_id for o in ordered_outcomes],
        }
        _write_summary(artifacts.summary_path, summary)

        return DayRunResult(
            run_id=run_id,
            valid_plans=valid_plans,
            rejected_plans=rejected_plans,
            outcomes=ordered_outcomes,
            artifacts=artifacts,
            summary=summary,
        )

    def run_from_trade_plans_path(
        self,
        trade_plans: list[TradePlan],
        *,
        replay_path: Path | str,
        output_root: Path | str,
        run_id: str,
    ) -> DayRunResult:
        """Production path entrypoint: always validates collection first."""
        replay_path = Path(replay_path)
        return self.run_from_trade_plans(
            trade_plans,
            replay_factory=lambda: BacktestReplay.from_validated_path(replay_path),
            output_root=output_root,
            run_id=run_id,
        )


def run_day_from_confirmations_path(
    confirmations: list[ConfirmationEvent],
    feature_records: list[FeatureRecord],
    *,
    replay_path: Path | str,
    output_root: Path | str,
    run_id: str,
    plan_config: PlanConfig | None = None,
) -> DayRunResult:
    """Convenience wrapper for confirmation → plan → outcome day runs."""
    runner = DayRunner(plan_builder=PlanBuilder(plan_config))
    return runner.run_from_confirmations_path(
        confirmations,
        feature_records,
        replay_path=replay_path,
        output_root=output_root,
        run_id=run_id,
    )


def run_day_from_trade_plans_path(
    trade_plans: list[TradePlan],
    *,
    replay_path: Path | str,
    output_root: Path | str,
    run_id: str,
) -> DayRunResult:
    """Convenience wrapper for prebuilt-plan day runs."""
    return DayRunner().run_from_trade_plans_path(
        trade_plans,
        replay_path=replay_path,
        output_root=output_root,
        run_id=run_id,
    )


def _index_features(feature_records: list[FeatureRecord]) -> dict[int, FeatureRecord]:
    indexed: dict[int, FeatureRecord] = {}
    for record in feature_records:
        if record.candle_index in indexed:
            raise ValueError(
                f"duplicate FeatureRecord candle_index {record.candle_index}"
            )
        indexed[record.candle_index] = record
    return indexed


def _artifact_paths(output_root: Path, run_id: str) -> DayRunArtifacts:
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return DayRunArtifacts(
        run_id=run_id,
        output_dir=run_dir,
        trade_plans_path=run_dir / "trade_plans.jsonl",
        rejected_trade_plans_path=run_dir / "rejected_trade_plans.jsonl",
        trade_outcomes_path=run_dir / "trade_outcomes.jsonl",
        summary_path=run_dir / "day_runner_summary.json",
    )


def _write_jsonl_records(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, separators=(",", ":")) + "\n")


def _write_summary(path: Path, summary: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
