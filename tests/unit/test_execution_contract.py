"""Unit tests for Phase 5A.1 execution contract semantics."""
from __future__ import annotations

from src.simulator.execution_contract import (
    CandleExecutionView,
    ExecutionOutcome,
    can_scan_outcome_on_candle,
    outcome_scan_start_candle_index,
    resolve_candle_outcome,
    skip_rejected_plan,
    unresolved_at_end_of_replay,
)
from src.simulator.trade_plan import TradePlan, TradePlanDirection, PlanStatus


def _valid_long_plan(**overrides) -> TradePlan:
    base = dict(
        plan_id="TSLA_2024-01-15_00011",
        timestamp=1705334400,
        symbol="TSLA",
        timeframe="2",
        replay_date="2024-01-15",
        candle_index=11,
        setup_type="FAILED_LTP",
        watch_type="FAILED_LTP_WATCH",
        grade="B",
        source_candle_index=10,
        direction=TradePlanDirection.LONG,
        entry_trigger=200.0,
        stop=198.0,
        risk=2.0,
        target_1_5r=203.0,
        reward_risk=1.5,
        invalidation="Invalidated if price commits decisively in the opposite direction.",
        plan_status=PlanStatus.VALID,
        rejection_reason=None,
    )
    base.update(overrides)
    return TradePlan(**base)


def _valid_short_plan(**overrides) -> TradePlan:
    return _valid_long_plan(
        direction=TradePlanDirection.SHORT,
        entry_trigger=200.0,
        stop=202.0,
        risk=2.0,
        target_1_5r=197.0,
        **overrides,
    )


def _candle(idx: int, *, open_: float, high: float, low: float) -> CandleExecutionView:
    return CandleExecutionView(candle_index=idx, open=open_, high=high, low=low)


class TestScanStartRules:
    def test_outcome_scan_starts_after_eval_candle(self):
        plan = _valid_long_plan(candle_index=11)
        assert outcome_scan_start_candle_index(plan) == 12

    def test_same_eval_candle_cannot_determine_outcome(self):
        plan = _valid_long_plan(candle_index=11)
        candle = _candle(11, open_=200.0, high=205.0, low=197.0)
        assert can_scan_outcome_on_candle(plan, 11) is False
        assert resolve_candle_outcome(plan, candle) is None

    def test_outcome_scan_starts_at_candle_index_plus_one(self):
        plan = _valid_long_plan(candle_index=11)
        assert can_scan_outcome_on_candle(plan, 12) is True


class TestIntrabarResolution:
    def test_target_before_stop_for_long_when_only_target_touched(self):
        plan = _valid_long_plan()
        decision = resolve_candle_outcome(
            plan,
            _candle(12, open_=200.5, high=203.5, low=199.5),
        )
        assert decision is not None
        assert decision.outcome == ExecutionOutcome.TARGET_BEFORE_STOP
        assert decision.realized_r == 1.5
        assert decision.counts_as_win is True

    def test_stop_before_target_for_long_when_only_stop_touched(self):
        plan = _valid_long_plan()
        decision = resolve_candle_outcome(
            plan,
            _candle(12, open_=199.5, high=202.5, low=197.5),
        )
        assert decision is not None
        assert decision.outcome == ExecutionOutcome.STOP_BEFORE_TARGET
        assert decision.realized_r == -1.0
        assert decision.counts_as_loss is True

    def test_both_stop_and_target_same_candle_becomes_ambiguous(self):
        plan = _valid_long_plan()
        decision = resolve_candle_outcome(
            plan,
            _candle(12, open_=200.0, high=203.5, low=197.5),
        )
        assert decision is not None
        assert decision.outcome == ExecutionOutcome.AMBIGUOUS_BOTH_TOUCHED
        assert decision.realized_r is None
        assert decision.counts_as_win is False
        assert decision.counts_as_loss is False


class TestGapResolution:
    def test_gap_beyond_stop_handled_deterministically_for_long(self):
        plan = _valid_long_plan()
        decision = resolve_candle_outcome(
            plan,
            _candle(12, open_=197.0, high=198.0, low=196.5),
        )
        assert decision is not None
        assert decision.outcome == ExecutionOutcome.GAP_BEYOND_STOP
        assert decision.realized_r == -1.0

    def test_gap_beyond_target_handled_deterministically_for_long(self):
        plan = _valid_long_plan()
        decision = resolve_candle_outcome(
            plan,
            _candle(12, open_=204.0, high=204.5, low=203.5),
        )
        assert decision is not None
        assert decision.outcome == ExecutionOutcome.GAP_BEYOND_TARGET
        assert decision.realized_r == 1.5

    def test_gap_beyond_stop_handled_deterministically_for_short(self):
        plan = _valid_short_plan()
        decision = resolve_candle_outcome(
            plan,
            _candle(12, open_=202.5, high=203.0, low=201.5),
        )
        assert decision is not None
        assert decision.outcome == ExecutionOutcome.GAP_BEYOND_STOP
        assert decision.realized_r == -1.0

    def test_gap_beyond_target_handled_deterministically_for_short(self):
        plan = _valid_short_plan()
        decision = resolve_candle_outcome(
            plan,
            _candle(12, open_=196.5, high=197.0, low=196.0),
        )
        assert decision is not None
        assert decision.outcome == ExecutionOutcome.GAP_BEYOND_TARGET
        assert decision.realized_r == 1.5


class TestTerminalContractOutcomes:
    def test_unresolved_at_end_handled_deterministically(self):
        plan = _valid_long_plan()
        decision = unresolved_at_end_of_replay(plan)
        assert decision.outcome == ExecutionOutcome.UNRESOLVED_END_OF_REPLAY
        assert decision.realized_r is None
        assert decision.counts_as_win is False
        assert decision.counts_as_loss is False

    def test_rejected_plan_is_skipped(self):
        plan = _valid_long_plan(
            plan_status=PlanStatus.REJECTED_NOT_TRADABLE,
            rejection_reason="not executable",
        )
        decision = skip_rejected_plan(plan)
        assert decision.outcome == ExecutionOutcome.SKIPPED_REJECTED_PLAN
        assert decision.realized_r is None

    def test_resolve_candle_outcome_skips_rejected_plan(self):
        plan = _valid_long_plan(
            plan_status=PlanStatus.REJECTED_NOT_TRADABLE,
            rejection_reason="not executable",
        )
        decision = resolve_candle_outcome(
            plan,
            _candle(12, open_=204.0, high=204.5, low=203.5),
        )
        assert decision is not None
        assert decision.outcome == ExecutionOutcome.SKIPPED_REJECTED_PLAN
