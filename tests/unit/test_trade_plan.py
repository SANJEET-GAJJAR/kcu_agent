"""Unit tests for TradePlan dataclass (Phase 5A).

Covers:
  - TradePlanDirection and PlanStatus enumerations
  - TradePlan construction and field constraints
  - validate() correctness for VALID and rejected plans
  - Serialisation round-trip (to_dict / from_dict / to_jsonl_line)
  - No outcome fields present on TradePlan
"""
from __future__ import annotations

import json

import pytest

from src.simulator.trade_plan import TradePlan, TradePlanDirection, PlanStatus


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def _valid_plan(**overrides) -> TradePlan:
    defaults = dict(
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
    defaults.update(overrides)
    return TradePlan(**defaults)


def _rejected_plan(status: str = PlanStatus.REJECTED_NOT_CONFIRMED, **overrides) -> TradePlan:
    defaults = dict(
        plan_id="TSLA_2024-01-15_00011",
        timestamp=1705334400,
        symbol="TSLA",
        timeframe="2",
        replay_date="2024-01-15",
        candle_index=11,
        setup_type="CHOP",
        watch_type="CHOP",
        grade=None,
        source_candle_index=10,
        direction=TradePlanDirection.UNKNOWN,
        entry_trigger=None,
        stop=None,
        risk=None,
        target_1_5r=None,
        reward_risk=None,
        invalidation="Invalidated if price returns inside the pre-breakout range.",
        plan_status=status,
        rejection_reason="test rejection reason",
    )
    defaults.update(overrides)
    return TradePlan(**defaults)


# ---------------------------------------------------------------------------
# TradePlanDirection
# ---------------------------------------------------------------------------

class TestTradePlanDirection:
    def test_long_value(self):
        assert TradePlanDirection.LONG == "long"

    def test_short_value(self):
        assert TradePlanDirection.SHORT == "short"

    def test_unknown_value(self):
        assert TradePlanDirection.UNKNOWN == "unknown"

    def test_all_values_set(self):
        assert TradePlanDirection.ALL_VALUES == {"long", "short", "unknown"}

    def test_all_values_is_frozenset(self):
        assert isinstance(TradePlanDirection.ALL_VALUES, frozenset)

    def test_all_three_in_all_values(self):
        for v in (TradePlanDirection.LONG, TradePlanDirection.SHORT, TradePlanDirection.UNKNOWN):
            assert v in TradePlanDirection.ALL_VALUES


# ---------------------------------------------------------------------------
# PlanStatus
# ---------------------------------------------------------------------------

class TestPlanStatus:
    def test_valid_value(self):
        assert PlanStatus.VALID == "VALID"

    def test_rejected_not_confirmed_value(self):
        assert PlanStatus.REJECTED_NOT_CONFIRMED == "REJECTED_NOT_CONFIRMED"

    def test_rejected_unsupported_type_value(self):
        assert PlanStatus.REJECTED_UNSUPPORTED_TYPE == "REJECTED_UNSUPPORTED_TYPE"

    def test_rejected_not_tradable_value(self):
        assert PlanStatus.REJECTED_NOT_TRADABLE == "REJECTED_NOT_TRADABLE"

    def test_rejected_event_feature_mismatch_value(self):
        assert PlanStatus.REJECTED_EVENT_FEATURE_MISMATCH == "REJECTED_EVENT_FEATURE_MISMATCH"

    def test_rejected_missing_fields_value(self):
        assert PlanStatus.REJECTED_MISSING_FIELDS == "REJECTED_MISSING_FIELDS"

    def test_rejected_rr_below_minimum_value(self):
        assert PlanStatus.REJECTED_RR_BELOW_MINIMUM == "REJECTED_RR_BELOW_MINIMUM"

    def test_all_values_contains_all_statuses(self):
        expected = {
            "VALID",
            "REJECTED_NOT_CONFIRMED",
            "REJECTED_UNSUPPORTED_TYPE",
            "REJECTED_NOT_TRADABLE",
            "REJECTED_EVENT_FEATURE_MISMATCH",
            "REJECTED_MISSING_FIELDS",
            "REJECTED_RR_BELOW_MINIMUM",
        }
        assert PlanStatus.ALL_VALUES == expected

    def test_all_values_is_frozenset(self):
        assert isinstance(PlanStatus.ALL_VALUES, frozenset)

    def test_rejected_not_tradable_is_distinct_from_not_confirmed(self):
        assert PlanStatus.REJECTED_NOT_TRADABLE != PlanStatus.REJECTED_NOT_CONFIRMED

    def test_rejected_not_tradable_is_distinct_from_unsupported_type(self):
        assert PlanStatus.REJECTED_NOT_TRADABLE != PlanStatus.REJECTED_UNSUPPORTED_TYPE

    def test_rejected_event_feature_mismatch_is_distinct_from_missing_fields(self):
        assert PlanStatus.REJECTED_EVENT_FEATURE_MISMATCH != PlanStatus.REJECTED_MISSING_FIELDS


# ---------------------------------------------------------------------------
# TradePlan: construction
# ---------------------------------------------------------------------------

class TestTradePlanConstruction:
    def test_valid_plan_has_all_fields(self):
        plan = _valid_plan()
        assert plan.entry_trigger == 200.0
        assert plan.stop == 198.0
        assert plan.risk == 2.0
        assert plan.target_1_5r == 203.0
        assert plan.reward_risk == 1.5

    def test_rejected_plan_has_none_price_fields(self):
        plan = _rejected_plan()
        assert plan.entry_trigger is None
        assert plan.stop is None
        assert plan.risk is None
        assert plan.target_1_5r is None
        assert plan.reward_risk is None

    def test_plan_id_is_string(self):
        assert isinstance(_valid_plan().plan_id, str)

    def test_grade_can_be_none(self):
        plan = _valid_plan(grade=None)
        assert plan.grade is None

    def test_grade_a(self):
        plan = _valid_plan(grade="A")
        assert plan.grade == "A"

    def test_rejection_reason_none_for_valid(self):
        plan = _valid_plan()
        assert plan.rejection_reason is None

    def test_rejection_reason_set_for_rejected(self):
        plan = _rejected_plan()
        assert plan.rejection_reason is not None

    def test_source_candle_index_tracked(self):
        plan = _valid_plan(source_candle_index=7)
        assert plan.source_candle_index == 7

    def test_direction_long(self):
        plan = _valid_plan(direction=TradePlanDirection.LONG)
        assert plan.direction == "long"

    def test_direction_short(self):
        plan = _valid_plan(
            direction=TradePlanDirection.SHORT, stop=202.0, risk=2.0, target_1_5r=197.0,
        )
        assert plan.direction == "short"


# ---------------------------------------------------------------------------
# TradePlan: is_valid
# ---------------------------------------------------------------------------

class TestIsValid:
    def test_valid_plan_returns_true(self):
        assert _valid_plan().is_valid() is True

    def test_rejected_not_confirmed_returns_false(self):
        assert _rejected_plan(PlanStatus.REJECTED_NOT_CONFIRMED).is_valid() is False

    def test_rejected_unsupported_returns_false(self):
        assert _rejected_plan(PlanStatus.REJECTED_UNSUPPORTED_TYPE).is_valid() is False

    def test_rejected_not_tradable_returns_false(self):
        assert _rejected_plan(PlanStatus.REJECTED_NOT_TRADABLE).is_valid() is False

    def test_rejected_missing_fields_returns_false(self):
        assert _rejected_plan(PlanStatus.REJECTED_MISSING_FIELDS).is_valid() is False

    def test_rejected_rr_below_minimum_returns_false(self):
        assert _rejected_plan(PlanStatus.REJECTED_RR_BELOW_MINIMUM).is_valid() is False


# ---------------------------------------------------------------------------
# TradePlan: validate()
# ---------------------------------------------------------------------------

class TestTradePlanValidate:
    def test_valid_plan_no_errors(self):
        assert _valid_plan().validate() == []

    def test_rejected_plan_no_errors(self):
        assert _rejected_plan().validate() == []

    def test_rejected_not_tradable_plan_no_errors(self):
        assert _rejected_plan(PlanStatus.REJECTED_NOT_TRADABLE).validate() == []

    def test_zero_timestamp_fails(self):
        errors = _valid_plan(timestamp=0).validate()
        assert any("timestamp" in e for e in errors)

    def test_negative_timestamp_fails(self):
        errors = _valid_plan(timestamp=-1).validate()
        assert any("timestamp" in e for e in errors)

    def test_empty_symbol_fails(self):
        errors = _valid_plan(symbol="").validate()
        assert any("symbol" in e for e in errors)

    def test_empty_timeframe_fails(self):
        errors = _valid_plan(timeframe="").validate()
        assert any("timeframe" in e for e in errors)

    def test_empty_replay_date_fails(self):
        errors = _valid_plan(replay_date="").validate()
        assert any("replay_date" in e for e in errors)

    def test_negative_candle_index_fails(self):
        errors = _valid_plan(candle_index=-1).validate()
        assert any("candle_index" in e for e in errors)

    def test_negative_source_candle_index_fails(self):
        errors = _valid_plan(source_candle_index=-1).validate()
        assert any("source_candle_index" in e for e in errors)

    def test_invalid_direction_fails(self):
        errors = _valid_plan(direction="sideways").validate()
        assert any("direction" in e for e in errors)

    def test_invalid_plan_status_fails(self):
        errors = _valid_plan(plan_status="MAYBE").validate()
        assert any("plan_status" in e for e in errors)

    def test_valid_plan_with_unknown_direction_fails(self):
        errors = _valid_plan(direction=TradePlanDirection.UNKNOWN).validate()
        assert any("direction" in e for e in errors)

    def test_valid_plan_missing_entry_trigger_fails(self):
        errors = _valid_plan(entry_trigger=None).validate()
        assert any("entry_trigger" in e for e in errors)

    def test_valid_plan_missing_stop_fails(self):
        errors = _valid_plan(stop=None).validate()
        assert any("stop" in e for e in errors)

    def test_valid_plan_missing_risk_fails(self):
        errors = _valid_plan(risk=None).validate()
        assert any("risk" in e for e in errors)

    def test_valid_plan_missing_target_fails(self):
        errors = _valid_plan(target_1_5r=None).validate()
        assert any("target_1_5r" in e for e in errors)

    def test_valid_plan_missing_reward_risk_fails(self):
        errors = _valid_plan(reward_risk=None).validate()
        assert any("reward_risk" in e for e in errors)

    def test_rejected_plan_missing_rejection_reason_fails(self):
        errors = _rejected_plan(rejection_reason=None).validate()
        assert any("rejection_reason" in e for e in errors)

    def test_all_rejected_statuses_require_reason(self):
        for status in (
            PlanStatus.REJECTED_NOT_CONFIRMED,
            PlanStatus.REJECTED_UNSUPPORTED_TYPE,
            PlanStatus.REJECTED_NOT_TRADABLE,
            PlanStatus.REJECTED_MISSING_FIELDS,
            PlanStatus.REJECTED_RR_BELOW_MINIMUM,
        ):
            plan = _rejected_plan(status, rejection_reason=None)
            errors = plan.validate()
            assert any("rejection_reason" in e for e in errors), \
                f"Expected rejection_reason error for status={status}"


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

class TestTradePlanSerialisation:
    def test_to_dict_valid_plan(self):
        plan = _valid_plan()
        d = plan.to_dict()
        assert d["entry_trigger"] == 200.0
        assert d["stop"] == 198.0
        assert d["risk"] == 2.0
        assert d["target_1_5r"] == 203.0
        assert d["reward_risk"] == 1.5
        assert d["plan_status"] == "VALID"
        assert d["rejection_reason"] is None

    def test_to_dict_rejected_plan_has_none_fields(self):
        plan = _rejected_plan()
        d = plan.to_dict()
        assert d["entry_trigger"] is None
        assert d["stop"] is None
        assert d["risk"] is None
        assert d["target_1_5r"] is None
        assert d["reward_risk"] is None

    def test_from_dict_round_trip_valid(self):
        plan = _valid_plan()
        rebuilt = TradePlan.from_dict(plan.to_dict())
        assert rebuilt.to_dict() == plan.to_dict()

    def test_from_dict_round_trip_rejected(self):
        plan = _rejected_plan()
        rebuilt = TradePlan.from_dict(plan.to_dict())
        assert rebuilt.to_dict() == plan.to_dict()

    def test_from_dict_round_trip_rejected_not_tradable(self):
        plan = _rejected_plan(PlanStatus.REJECTED_NOT_TRADABLE)
        rebuilt = TradePlan.from_dict(plan.to_dict())
        assert rebuilt.plan_status == PlanStatus.REJECTED_NOT_TRADABLE
        assert rebuilt.to_dict() == plan.to_dict()

    def test_to_jsonl_line_is_single_line(self):
        line = _valid_plan().to_jsonl_line()
        assert "\n" not in line

    def test_to_jsonl_line_is_valid_json(self):
        line = _valid_plan().to_jsonl_line()
        parsed = json.loads(line)
        assert parsed["plan_status"] == "VALID"

    def test_from_dict_all_rejected_statuses(self):
        for status in PlanStatus.ALL_VALUES:
            if status == PlanStatus.VALID:
                plan = _valid_plan(plan_status=status)
            else:
                plan = _rejected_plan(status)
            rebuilt = TradePlan.from_dict(plan.to_dict())
            assert rebuilt.plan_status == status

    def test_grade_none_preserved_in_round_trip(self):
        plan = _valid_plan(grade=None)
        rebuilt = TradePlan.from_dict(plan.to_dict())
        assert rebuilt.grade is None

    def test_grade_value_preserved_in_round_trip(self):
        plan = _valid_plan(grade="A")
        rebuilt = TradePlan.from_dict(plan.to_dict())
        assert rebuilt.grade == "A"

    def test_rejected_not_tradable_serialises_with_reason(self):
        plan = _rejected_plan(
            PlanStatus.REJECTED_NOT_TRADABLE,
            rejection_reason="CHOP is a no-trade condition",
        )
        d = plan.to_dict()
        assert d["plan_status"] == "REJECTED_NOT_TRADABLE"
        assert d["rejection_reason"] == "CHOP is a no-trade condition"


# ---------------------------------------------------------------------------
# No outcome fields
# ---------------------------------------------------------------------------

class TestNoOutcomeFields:
    """TradePlan must not carry any outcome, win/loss, or performance fields."""

    def test_no_outcome_field(self):
        plan = _valid_plan()
        assert not hasattr(plan, "outcome")

    def test_no_win_field(self):
        plan = _valid_plan()
        assert not hasattr(plan, "win")

    def test_no_loss_field(self):
        plan = _valid_plan()
        assert not hasattr(plan, "loss")

    def test_no_pnl_field(self):
        plan = _valid_plan()
        assert not hasattr(plan, "pnl")

    def test_no_result_field(self):
        plan = _valid_plan()
        assert not hasattr(plan, "result")

    def test_no_hit_target_field(self):
        plan = _valid_plan()
        assert not hasattr(plan, "hit_target")

    def test_no_hit_stop_field(self):
        plan = _valid_plan()
        assert not hasattr(plan, "hit_stop")

    def test_no_fill_price_field(self):
        plan = _valid_plan()
        assert not hasattr(plan, "fill_price")

    def test_module_has_no_statistics_terms(self):
        import inspect
        import src.simulator.trade_plan as module
        source = inspect.getsource(module)
        forbidden = ["win_rate", "sharpe", "drawdown", "expectancy"]
        for term in forbidden:
            assert term not in source, f"Found forbidden term {term!r} in trade_plan.py"
