"""Unit tests for Phase 5C day runner and persistence."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.collector.candle_record import build_record
from src.collector.candle_schema import CandleSnapshot
from src.collector.chart_preflight import PreflightResult, StaleCollectionError, write_preflight_companion
from src.collector.jsonl_store import JsonlStore
from src.detectors.confirmation_event import ConfirmationEvent, ConfirmationOutcome
from src.detectors.kcu_candidate_contract import KCUSourceStatus
from src.features.feature_record import FeatureRecord
from src.simulator.day_runner import (
    DayRunner,
    run_day_from_confirmations_path,
    run_day_from_trade_plans_path,
)
from src.simulator.plan_builder import PlanConfig
from src.simulator.trade_plan import TradePlan, TradePlanDirection, PlanStatus


TS0 = 1705329000
STEP = 120


def _write_day(path: Path, candles: list[dict[str, float]]) -> Path:
    with JsonlStore(path) as store:
        for i, c in enumerate(candles):
            snap = CandleSnapshot(
                timestamp=TS0 + i * STEP,
                open=c["open"],
                high=c["high"],
                low=c["low"],
                close=c["close"],
                volume=1000.0 + i,
                symbol="TSLA",
                timeframe="2",
                replay_date="2024-01-15",
            )
            store.append(build_record(snap, {}, i))
    return path


def _valid_preflight() -> PreflightResult:
    return PreflightResult(
        template_name="only KCU indicator",
        indicator_names=["Stop Loss Widget", "KCU Indicator", "Volume"],
        required_indicators_present=True,
        kcu_indicator_version="1.2.3",
        preflight_passed=True,
        collection_version="1.0.0",
        collector_version="1.0.0",
        failure_reasons=[],
    )


def _feature(
    *,
    candle_index: int,
    open_: float,
    high: float,
    low: float,
    close: float,
    session: str = "regular",
    time_since_open_minutes: float = 32.0,
) -> FeatureRecord:
    rng = high - low
    body = abs(close - open_)
    return FeatureRecord(
        timestamp=TS0 + candle_index * STEP,
        symbol="TSLA",
        timeframe="2",
        replay_date="2024-01-15",
        candle_index=candle_index,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=500_000.0,
        candle_body=body,
        upper_wick=high - max(close, open_),
        lower_wick=min(close, open_) - low,
        body_pct=(body / rng * 100) if rng > 0 else None,
        candle_range=rng,
        atr=1.5,
        gap_from_prev=None,
        distance_from_prev_close=None,
        is_higher_high=True,
        is_lower_low=False,
        is_inside_bar=False,
        is_outside_bar=False,
        consecutive_hh=1,
        consecutive_ll=0,
        consecutive_lh=0,
        consecutive_hl=0,
        relative_volume=1.2,
        session=session,
        time_since_open_minutes=time_since_open_minutes,
        distance_from_session_open=2.0,
        indicators={},
    )


def _confirmed_event(**overrides) -> ConfirmationEvent:
    base = dict(
        timestamp=TS0,
        symbol="TSLA",
        timeframe="2",
        replay_date="2024-01-15",
        candle_index=0,
        evaluated_at_candle_index=1,
        evaluated_at_timestamp=TS0 + STEP,
        watch_type="FAILED_LTP_WATCH",
        setup_type="FAILED_LTP",
        outcome=ConfirmationOutcome.CONFIRMED_SETUP,
        grade="B",
        source_status=KCUSourceStatus.CONFIRMED,
        confirmed_components=["prior_compression", "expansion_failure"],
        missing_components=[],
        invalidating_components=[],
        reasons=["Setup confirmed"],
        reason_codes=["ALL_COMPONENTS_VERIFIED"],
        candidate_candle_index=0,
        candidate_timestamp=TS0,
        candidate_reason_codes=[],
    )
    base.update(overrides)
    return ConfirmationEvent(**base)


def _rejected_event(**overrides) -> ConfirmationEvent:
    base = dict(
        timestamp=TS0,
        symbol="TSLA",
        timeframe="2",
        replay_date="2024-01-15",
        candle_index=0,
        evaluated_at_candle_index=1,
        evaluated_at_timestamp=TS0 + STEP,
        watch_type="LTP_WATCH",
        setup_type="LTP",
        outcome=ConfirmationOutcome.REJECTED_SETUP,
        grade=None,
        source_status=KCUSourceStatus.HYPOTHESIS,
        confirmed_components=["patience_candle"],
        missing_components=["level_context", "trend_context"],
        invalidating_components=[],
        reasons=["level_context unverified"],
        reason_codes=["LEVEL_CONTEXT_UNVERIFIED"],
        candidate_candle_index=0,
        candidate_timestamp=TS0,
        candidate_reason_codes=[],
    )
    base.update(overrides)
    return ConfirmationEvent(**base)


def _plan(**overrides) -> TradePlan:
    base = dict(
        plan_id="TSLA_2024-01-15_00001",
        timestamp=TS0 + STEP,
        symbol="TSLA",
        timeframe="2",
        replay_date="2024-01-15",
        candle_index=1,
        setup_type="FAILED_LTP",
        watch_type="FAILED_LTP_WATCH",
        grade="B",
        source_candle_index=0,
        direction=TradePlanDirection.LONG,
        entry_trigger=100.0,
        stop=98.0,
        risk=2.0,
        target_1_5r=103.0,
        reward_risk=1.5,
        invalidation="Invalidated if price commits decisively in the opposite direction.",
        plan_status=PlanStatus.VALID,
        rejection_reason=None,
    )
    base.update(overrides)
    return TradePlan(**base)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class TestDayRunner:
    def test_premarket_trade_plan_blocked_but_regular_trade_plan_still_possible(self, tmp_path):
        replay_path = _write_day(
            tmp_path / "TSLA_2024-01-15_2m.jsonl",
            [
                {"open": 99.0, "high": 101.0, "low": 98.5, "close": 100.0},
                {"open": 100.0, "high": 104.0, "low": 97.0, "close": 100.0},
                {"open": 100.5, "high": 103.5, "low": 99.5, "close": 103.0},
            ],
        )
        write_preflight_companion(_valid_preflight(), replay_path)

        result = run_day_from_confirmations_path(
            [
                _confirmed_event(
                    candidate_candle_index=0,
                    candle_index=0,
                    evaluated_at_candle_index=1,
                    evaluated_at_timestamp=TS0 + STEP,
                ),
                _confirmed_event(
                    candidate_candle_index=2,
                    candle_index=2,
                    evaluated_at_candle_index=2,
                    evaluated_at_timestamp=TS0 + 2 * STEP,
                    candidate_timestamp=TS0 + 2 * STEP,
                    timestamp=TS0 + 2 * STEP,
                ),
            ],
            [
                _feature(candle_index=0, open_=99.0, high=101.0, low=98.5, close=100.0),
                _feature(
                    candle_index=1,
                    open_=99.0,
                    high=101.0,
                    low=98.0,
                    close=100.0,
                    session="premarket",
                    time_since_open_minutes=-5.0,
                ),
                _feature(candle_index=2, open_=99.0, high=101.0, low=98.0, close=100.0),
            ],
            replay_path=replay_path,
            output_root=tmp_path / "outputs",
            run_id="run-session-gate",
            plan_config=PlanConfig(tradable_setup_types=frozenset({"FAILED_LTP"})),
        )

        assert len(result.valid_plans) == 1
        assert len(result.rejected_plans) == 1
        assert len(result.outcomes) == 1
        assert result.rejected_plans[0].plan_status == PlanStatus.REJECTED_NOT_TRADABLE
        assert "premarket/context-only" in result.rejected_plans[0].rejection_reason

    def test_valid_plans_persisted_rejected_persisted_outcomes_persisted(self, tmp_path):
        replay_path = _write_day(
            tmp_path / "TSLA_2024-01-15_2m.jsonl",
            [
                {"open": 99.0, "high": 101.0, "low": 98.5, "close": 100.0},
                {"open": 100.0, "high": 104.0, "low": 97.0, "close": 100.0},
                {"open": 100.5, "high": 103.5, "low": 99.5, "close": 103.0},
            ],
        )
        write_preflight_companion(_valid_preflight(), replay_path)

        result = run_day_from_confirmations_path(
            [_confirmed_event(), _rejected_event()],
            [
                _feature(candle_index=0, open_=99.0, high=101.0, low=98.5, close=100.0),
                _feature(candle_index=1, open_=99.0, high=101.0, low=98.0, close=100.0),
            ],
            replay_path=replay_path,
            output_root=tmp_path / "outputs",
            run_id="run-001",
            plan_config=PlanConfig(tradable_setup_types=frozenset({"FAILED_LTP"})),
        )

        valid_records = _read_jsonl(result.artifacts.trade_plans_path)
        rejected_records = _read_jsonl(result.artifacts.rejected_trade_plans_path)
        outcome_records = _read_jsonl(result.artifacts.trade_outcomes_path)
        summary = json.loads(result.artifacts.summary_path.read_text(encoding="utf-8"))

        assert len(valid_records) == 1
        assert len(rejected_records) == 1
        assert len(outcome_records) == 1
        assert valid_records[0]["run_id"] == "run-001"
        assert rejected_records[0]["run_id"] == "run-001"
        assert outcome_records[0]["run_id"] == "run-001"
        assert "audit_trail" in outcome_records[0]
        assert summary["valid_trade_plan_count"] == 1
        assert summary["rejected_trade_plan_count"] == 1
        assert summary["trade_outcome_count"] == 1

    def test_rejected_plans_are_not_simulated(self, tmp_path):
        replay_path = _write_day(
            tmp_path / "TSLA_2024-01-15_2m.jsonl",
            [
                {"open": 99.0, "high": 101.0, "low": 98.5, "close": 100.0},
                {"open": 100.0, "high": 104.0, "low": 97.0, "close": 100.0},
                {"open": 104.0, "high": 104.5, "low": 103.5, "close": 104.2},
            ],
        )
        write_preflight_companion(_valid_preflight(), replay_path)

        result = run_day_from_trade_plans_path(
            [
                _plan(
                    plan_status=PlanStatus.REJECTED_NOT_TRADABLE,
                    rejection_reason="not executable",
                )
            ],
            replay_path=replay_path,
            output_root=tmp_path / "outputs",
            run_id="run-002",
        )

        assert result.valid_plans == []
        assert len(result.rejected_plans) == 1
        assert result.outcomes == []
        assert _read_jsonl(result.artifacts.trade_outcomes_path) == []

    def test_runner_is_deterministic_across_repeated_runs(self, tmp_path):
        replay_path = _write_day(
            tmp_path / "TSLA_2024-01-15_2m.jsonl",
            [
                {"open": 99.0, "high": 101.0, "low": 98.5, "close": 100.0},
                {"open": 100.0, "high": 104.0, "low": 97.0, "close": 100.0},
                {"open": 100.5, "high": 103.5, "low": 99.5, "close": 103.0},
            ],
        )
        write_preflight_companion(_valid_preflight(), replay_path)

        plan = _plan()
        result_a = run_day_from_trade_plans_path(
            [plan],
            replay_path=replay_path,
            output_root=tmp_path / "outputs",
            run_id="run-003",
        )
        first_snapshot = {
            "plans": result_a.artifacts.trade_plans_path.read_text(encoding="utf-8"),
            "rejected": result_a.artifacts.rejected_trade_plans_path.read_text(encoding="utf-8"),
            "outcomes": result_a.artifacts.trade_outcomes_path.read_text(encoding="utf-8"),
            "summary": result_a.artifacts.summary_path.read_text(encoding="utf-8"),
        }

        result_b = run_day_from_trade_plans_path(
            [plan],
            replay_path=replay_path,
            output_root=tmp_path / "outputs",
            run_id="run-003",
        )
        second_snapshot = {
            "plans": result_b.artifacts.trade_plans_path.read_text(encoding="utf-8"),
            "rejected": result_b.artifacts.rejected_trade_plans_path.read_text(encoding="utf-8"),
            "outcomes": result_b.artifacts.trade_outcomes_path.read_text(encoding="utf-8"),
            "summary": result_b.artifacts.summary_path.read_text(encoding="utf-8"),
        }

        assert first_snapshot == second_snapshot

    def test_run_id_prevents_output_confusion(self, tmp_path):
        replay_path = _write_day(
            tmp_path / "TSLA_2024-01-15_2m.jsonl",
            [
                {"open": 99.0, "high": 101.0, "low": 98.5, "close": 100.0},
                {"open": 100.0, "high": 104.0, "low": 97.0, "close": 100.0},
                {"open": 100.5, "high": 103.5, "low": 99.5, "close": 103.0},
            ],
        )
        write_preflight_companion(_valid_preflight(), replay_path)

        result_one = run_day_from_trade_plans_path(
            [_plan()],
            replay_path=replay_path,
            output_root=tmp_path / "outputs",
            run_id="run-alpha",
        )
        result_two = run_day_from_trade_plans_path(
            [_plan()],
            replay_path=replay_path,
            output_root=tmp_path / "outputs",
            run_id="run-beta",
        )

        assert result_one.artifacts.output_dir != result_two.artifacts.output_dir
        assert result_one.artifacts.output_dir.name == "run-alpha"
        assert result_two.artifacts.output_dir.name == "run-beta"

    def test_runner_uses_validated_path_for_production_inputs(self, tmp_path):
        replay_path = _write_day(
            tmp_path / "TSLA_2024-01-15_2m.jsonl",
            [
                {"open": 99.0, "high": 101.0, "low": 98.5, "close": 100.0},
                {"open": 100.0, "high": 104.0, "low": 97.0, "close": 100.0},
                {"open": 100.5, "high": 103.5, "low": 99.5, "close": 103.0},
            ],
        )

        with pytest.raises(StaleCollectionError):
            run_day_from_trade_plans_path(
                [_plan()],
                replay_path=replay_path,
                output_root=tmp_path / "outputs",
                run_id="run-stale",
            )
