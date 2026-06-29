"""Unit tests for PlanBuilder (Phase 5A — post-semantics audit).

Semantics audit rules enforced here:
  - CHOP is a structural no-trade condition (never tradable, even when confirmed)
  - FAILED_LTP is disabled by default; requires explicit PlanConfig opt-in
  - Confirmed setup ≠ tradable setup (gate separate from confirmation check)
  - tradable_setup_types is empty by default — nothing tradable until explicitly enabled
  - Non-tradable confirmed setups produce REJECTED_NOT_TRADABLE (not VALID)

Acceptance criteria:
  - Confirmed setup CAN produce a valid TradePlan when explicitly enabled
  - Rejected setup (REJECTED_SETUP outcome) cannot produce a TradePlan
  - WATCH candidate cannot produce a TradePlan (only ConfirmationEvents accepted;
    WATCH events carry REJECTED_SETUP outcome → REJECTED_NOT_CONFIRMED)
  - Missing entry/stop/risk data rejects plan
  - R:R below minimum rejects plan
  - target_1_5r is calculated correctly
  - No future candles used
"""
from __future__ import annotations

import pytest

from src.detectors.confirmation_event import ConfirmationEvent, ConfirmationOutcome
from src.detectors.kcu_candidate_contract import KCUSourceStatus
from src.features.feature_record import FeatureRecord
from src.simulator.plan_builder import (
    PlanBuilder,
    PlanConfig,
    KNOWN_SETUP_TYPES,
    NON_TRADABLE_SETUP_TYPES,
    _infer_direction,
)
from src.simulator.trade_plan import TradePlan, TradePlanDirection, PlanStatus


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

_BASE_TS = 1705334400
_CANDLE_INTERVAL = 120  # 2-minute candles


def _confirmed_event(
    *,
    setup_type: str = "FAILED_LTP",
    watch_type: str = "FAILED_LTP_WATCH",
    grade: str = "B",
    candle_index: int = 10,
    evaluated_at_candle_index: int = 11,
    candidate_candle_index: int = 10,
    outcome: str = ConfirmationOutcome.CONFIRMED_SETUP,
    source_status: str = KCUSourceStatus.CONFIRMED,
) -> ConfirmationEvent:
    ts = _BASE_TS + candle_index * _CANDLE_INTERVAL
    eval_ts = _BASE_TS + evaluated_at_candle_index * _CANDLE_INTERVAL
    return ConfirmationEvent(
        timestamp=ts,
        symbol="TSLA",
        timeframe="2",
        replay_date="2024-01-15",
        candle_index=candle_index,
        evaluated_at_candle_index=evaluated_at_candle_index,
        evaluated_at_timestamp=eval_ts,
        watch_type=watch_type,
        setup_type=setup_type,
        outcome=outcome,
        grade=grade if outcome == ConfirmationOutcome.CONFIRMED_SETUP else None,
        source_status=source_status,
        confirmed_components=["contained_range"],
        missing_components=[],
        invalidating_components=[],
        reasons=["Setup confirmed"],
        reason_codes=[],
        candidate_candle_index=candidate_candle_index,
        candidate_timestamp=_BASE_TS + candidate_candle_index * _CANDLE_INTERVAL,
        candidate_reason_codes=[],
    )


def _rejected_confirmation(
    *,
    setup_type: str = "LTP",
    watch_type: str = "LTP_WATCH",
    candle_index: int = 10,
    evaluated_at_candle_index: int = 10,
) -> ConfirmationEvent:
    ts = _BASE_TS + candle_index * _CANDLE_INTERVAL
    return ConfirmationEvent(
        timestamp=ts,
        symbol="TSLA",
        timeframe="2",
        replay_date="2024-01-15",
        candle_index=candle_index,
        evaluated_at_candle_index=evaluated_at_candle_index,
        evaluated_at_timestamp=_BASE_TS + evaluated_at_candle_index * _CANDLE_INTERVAL,
        watch_type=watch_type,
        setup_type=setup_type,
        outcome=ConfirmationOutcome.REJECTED_SETUP,
        grade=None,
        source_status=KCUSourceStatus.HYPOTHESIS,
        confirmed_components=[],
        missing_components=["level_context", "trend_context"],
        invalidating_components=[],
        reasons=["level_context unverified"],
        reason_codes=["LEVEL_CONTEXT_UNVERIFIED"],
        candidate_candle_index=candle_index,
        candidate_timestamp=ts,
        candidate_reason_codes=[],
    )


def _eval_features(
    *,
    close: float,
    open_: float,
    high: float | None = None,
    low: float | None = None,
    candle_index: int = 11,
    session: str = "regular",
    time_since_open_minutes: float = 32.0,
) -> FeatureRecord:
    h = high if high is not None else max(close, open_) + 0.50
    lo = low if low is not None else min(close, open_) - 0.50
    body = abs(close - open_)
    rng = h - lo
    return FeatureRecord(
        timestamp=_BASE_TS + candle_index * _CANDLE_INTERVAL,
        symbol="TSLA",
        timeframe="2",
        replay_date="2024-01-15",
        candle_index=candle_index,
        open=open_,
        high=h,
        low=lo,
        close=close,
        volume=500_000.0,
        candle_body=body,
        upper_wick=h - max(close, open_),
        lower_wick=min(close, open_) - lo,
        body_pct=(body / rng * 100) if rng > 0 else None,
        candle_range=rng,
        atr=1.5,
        gap_from_prev=None,
        distance_from_prev_close=None,
        is_higher_high=True,
        is_lower_low=None,
        is_inside_bar=None,
        is_outside_bar=None,
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


def _enabled_config(*types: str) -> PlanConfig:
    """Create a PlanConfig with the given setup types explicitly enabled."""
    return PlanConfig(tradable_setup_types=frozenset(types))


# ---------------------------------------------------------------------------
# PlanConfig
# ---------------------------------------------------------------------------

class TestPlanConfig:
    def test_defaults(self):
        cfg = PlanConfig()
        assert cfg.target_r == 1.5
        assert cfg.min_rr_threshold == 1.5
        assert cfg.min_risk_dollars == 0.01

    def test_default_tradable_types_is_empty(self):
        """Nothing tradable by default — confirmed ≠ tradable."""
        cfg = PlanConfig()
        assert len(cfg.tradable_setup_types) == 0

    def test_tradable_types_is_frozenset(self):
        cfg = PlanConfig()
        assert isinstance(cfg.tradable_setup_types, frozenset)

    def test_custom_tradable_types(self):
        cfg = PlanConfig(tradable_setup_types=frozenset({"FAILED_LTP"}))
        assert "FAILED_LTP" in cfg.tradable_setup_types
        assert "CHOP" not in cfg.tradable_setup_types

    def test_premarket_trades_disabled_by_default(self):
        cfg = PlanConfig()
        assert cfg.allow_premarket_trades is False

    def test_can_enable_premarket_trades_explicitly(self):
        cfg = PlanConfig(allow_premarket_trades=True)
        assert cfg.allow_premarket_trades is True

    def test_custom_target_r(self):
        cfg = PlanConfig(target_r=2.0)
        assert cfg.target_r == 2.0

    def test_custom_min_rr_threshold(self):
        cfg = PlanConfig(min_rr_threshold=2.0)
        assert cfg.min_rr_threshold == 2.0

    def test_zero_target_r_raises(self):
        with pytest.raises(ValueError, match="target_r"):
            PlanConfig(target_r=0.0)

    def test_negative_target_r_raises(self):
        with pytest.raises(ValueError, match="target_r"):
            PlanConfig(target_r=-1.0)

    def test_zero_min_rr_threshold_raises(self):
        with pytest.raises(ValueError, match="min_rr_threshold"):
            PlanConfig(min_rr_threshold=0.0)

    def test_negative_min_risk_dollars_raises(self):
        with pytest.raises(ValueError, match="min_risk_dollars"):
            PlanConfig(min_risk_dollars=-0.01)

    def test_zero_min_risk_dollars_allowed(self):
        cfg = PlanConfig(min_risk_dollars=0.0)
        assert cfg.min_risk_dollars == 0.0


# ---------------------------------------------------------------------------
# Setup type registry constants
# ---------------------------------------------------------------------------

class TestSetupTypeRegistry:
    def test_known_setup_types_includes_all_kcu_types(self):
        for t in ("LTP", "REJECTION", "REVERSAL", "BOUNCE", "FAILED_LTP", "CHOP"):
            assert t in KNOWN_SETUP_TYPES, f"{t} missing from KNOWN_SETUP_TYPES"

    def test_known_setup_types_is_frozenset(self):
        assert isinstance(KNOWN_SETUP_TYPES, frozenset)

    def test_non_tradable_includes_chop(self):
        assert "CHOP" in NON_TRADABLE_SETUP_TYPES

    def test_non_tradable_is_frozenset(self):
        assert isinstance(NON_TRADABLE_SETUP_TYPES, frozenset)

    def test_failed_ltp_is_not_in_non_tradable(self):
        """FAILED_LTP is disabled by default but CAN be enabled via config."""
        assert "FAILED_LTP" not in NON_TRADABLE_SETUP_TYPES

    def test_ltp_is_not_in_non_tradable(self):
        """LTP should be tradable once level context is wired in."""
        assert "LTP" not in NON_TRADABLE_SETUP_TYPES


# ---------------------------------------------------------------------------
# CHOP: structural no-trade condition
# ---------------------------------------------------------------------------

class TestChopNeverTradable:
    """CHOP confirmed event always produces REJECTED_NOT_TRADABLE."""

    def test_chop_confirmed_is_rejected_not_tradable(self):
        builder = PlanBuilder()
        event = _confirmed_event(setup_type="CHOP", watch_type="CHOP")
        features = _eval_features(close=202.0, open_=200.0, high=203.0, low=199.0)
        plan = builder.build(event, features)
        assert plan.plan_status == PlanStatus.REJECTED_NOT_TRADABLE

    def test_chop_is_not_valid(self):
        builder = PlanBuilder()
        event = _confirmed_event(setup_type="CHOP", watch_type="CHOP")
        features = _eval_features(close=202.0, open_=200.0)
        plan = builder.build(event, features)
        assert not plan.is_valid()

    def test_chop_rejection_reason_mentions_no_trade_condition(self):
        builder = PlanBuilder()
        event = _confirmed_event(setup_type="CHOP", watch_type="CHOP")
        features = _eval_features(close=202.0, open_=200.0)
        plan = builder.build(event, features)
        assert plan.rejection_reason is not None
        reason_lower = plan.rejection_reason.lower()
        assert "no-trade" in reason_lower or "avoid" in reason_lower or "structural" in reason_lower

    def test_chop_cannot_be_enabled_by_adding_to_tradable_types(self):
        """NON_TRADABLE_SETUP_TYPES (CHOP) cannot be overridden by config."""
        cfg = PlanConfig(tradable_setup_types=frozenset({"CHOP"}))
        builder = PlanBuilder(cfg)
        event = _confirmed_event(setup_type="CHOP", watch_type="CHOP")
        features = _eval_features(close=202.0, open_=200.0)
        plan = builder.build(event, features)
        assert plan.plan_status == PlanStatus.REJECTED_NOT_TRADABLE

    def test_chop_no_entry_trigger(self):
        builder = PlanBuilder()
        event = _confirmed_event(setup_type="CHOP", watch_type="CHOP")
        features = _eval_features(close=202.0, open_=200.0, high=203.0, low=199.0)
        plan = builder.build(event, features)
        assert plan.entry_trigger is None

    def test_chop_no_stop(self):
        builder = PlanBuilder()
        event = _confirmed_event(setup_type="CHOP", watch_type="CHOP")
        features = _eval_features(close=202.0, open_=200.0, high=203.0, low=199.0)
        plan = builder.build(event, features)
        assert plan.stop is None

    def test_chop_no_target(self):
        builder = PlanBuilder()
        event = _confirmed_event(setup_type="CHOP", watch_type="CHOP")
        features = _eval_features(close=202.0, open_=200.0, high=203.0, low=199.0)
        plan = builder.build(event, features)
        assert plan.target_1_5r is None


# ---------------------------------------------------------------------------
# FAILED_LTP: disabled by default, can be enabled
# ---------------------------------------------------------------------------

class TestFailedLTPTradability:
    def test_failed_ltp_disabled_by_default(self):
        """Default config has no tradable types → FAILED_LTP is REJECTED_NOT_TRADABLE."""
        builder = PlanBuilder()
        event = _confirmed_event(setup_type="FAILED_LTP", watch_type="FAILED_LTP_WATCH")
        features = _eval_features(close=202.0, open_=200.0, high=203.0, low=199.0)
        plan = builder.build(event, features)
        assert plan.plan_status == PlanStatus.REJECTED_NOT_TRADABLE

    def test_failed_ltp_default_rejection_reason_mentions_config(self):
        builder = PlanBuilder()
        event = _confirmed_event(setup_type="FAILED_LTP", watch_type="FAILED_LTP_WATCH")
        features = _eval_features(close=202.0, open_=200.0)
        plan = builder.build(event, features)
        assert "tradable_setup_types" in plan.rejection_reason

    def test_failed_ltp_enabled_via_config_produces_valid_long_plan(self):
        """When explicitly enabled, FAILED_LTP with bullish eval candle → valid long plan."""
        cfg = _enabled_config("FAILED_LTP")
        builder = PlanBuilder(cfg)
        event = _confirmed_event(setup_type="FAILED_LTP", watch_type="FAILED_LTP_WATCH")
        features = _eval_features(close=202.0, open_=200.0, high=203.0, low=199.0)
        plan = builder.build(event, features)
        assert plan.is_valid()
        assert plan.plan_status == PlanStatus.VALID
        assert plan.direction == TradePlanDirection.LONG

    def test_failed_ltp_enabled_via_config_produces_valid_short_plan(self):
        """Bearish eval candle with FAILED_LTP enabled → valid short plan."""
        cfg = _enabled_config("FAILED_LTP")
        builder = PlanBuilder(cfg)
        event = _confirmed_event(setup_type="FAILED_LTP", watch_type="FAILED_LTP_WATCH")
        features = _eval_features(close=198.0, open_=200.0, high=201.0, low=197.0)
        plan = builder.build(event, features)
        assert plan.is_valid()
        assert plan.direction == TradePlanDirection.SHORT

    def test_failed_ltp_enabled_but_doji_candle_rejects(self):
        """Enabled but eval candle is doji (no body) → REJECTED_MISSING_FIELDS."""
        cfg = _enabled_config("FAILED_LTP")
        builder = PlanBuilder(cfg)
        event = _confirmed_event(setup_type="FAILED_LTP", watch_type="FAILED_LTP_WATCH")
        features = _eval_features(close=200.0, open_=200.0, high=201.0, low=199.0)
        plan = builder.build(event, features)
        assert plan.plan_status == PlanStatus.REJECTED_MISSING_FIELDS

    def test_failed_ltp_enabled_plan_validates_cleanly(self):
        cfg = _enabled_config("FAILED_LTP")
        builder = PlanBuilder(cfg)
        event = _confirmed_event(setup_type="FAILED_LTP", watch_type="FAILED_LTP_WATCH")
        features = _eval_features(close=202.0, open_=200.0, high=203.0, low=199.0)
        plan = builder.build(event, features)
        assert plan.validate() == []

    def test_failed_ltp_invalidation_text_set(self):
        cfg = _enabled_config("FAILED_LTP")
        builder = PlanBuilder(cfg)
        event = _confirmed_event(setup_type="FAILED_LTP", watch_type="FAILED_LTP_WATCH")
        features = _eval_features(close=202.0, open_=200.0, high=203.0, low=199.0)
        plan = builder.build(event, features)
        assert "opposite direction" in plan.invalidation

    def test_premarket_trade_plan_blocked_by_default(self):
        cfg = _enabled_config("FAILED_LTP")
        builder = PlanBuilder(cfg)
        event = _confirmed_event(setup_type="FAILED_LTP", watch_type="FAILED_LTP_WATCH")
        features = _eval_features(
            close=202.0,
            open_=200.0,
            high=203.0,
            low=199.0,
            session="premarket",
            time_since_open_minutes=-5.0,
        )
        plan = builder.build(event, features)
        assert plan.plan_status == PlanStatus.REJECTED_NOT_TRADABLE
        assert "premarket/context-only" in plan.rejection_reason

    def test_premarket_trade_plan_allowed_with_explicit_override(self):
        cfg = PlanConfig(
            tradable_setup_types=frozenset({"FAILED_LTP"}),
            allow_premarket_trades=True,
        )
        builder = PlanBuilder(cfg)
        event = _confirmed_event(setup_type="FAILED_LTP", watch_type="FAILED_LTP_WATCH")
        features = _eval_features(
            close=202.0,
            open_=200.0,
            high=203.0,
            low=199.0,
            session="premarket",
            time_since_open_minutes=-5.0,
        )
        plan = builder.build(event, features)
        assert plan.plan_status == PlanStatus.VALID
        assert plan.direction == TradePlanDirection.LONG


# ---------------------------------------------------------------------------
# Confirmed setup CAN produce valid TradePlan (acceptance criterion)
# ---------------------------------------------------------------------------

class TestConfirmedSetupCanProduceValidPlan:
    """Demonstrates that the builder CAN produce valid plans when type is enabled."""

    def test_explicitly_enabled_type_produces_valid_plan(self):
        cfg = _enabled_config("FAILED_LTP")
        builder = PlanBuilder(cfg)
        event = _confirmed_event(setup_type="FAILED_LTP", watch_type="FAILED_LTP_WATCH")
        features = _eval_features(close=202.0, open_=200.0, high=203.0, low=199.0)
        plan = builder.build(event, features)
        assert plan.is_valid()

    def test_valid_plan_has_all_price_fields(self):
        cfg = _enabled_config("FAILED_LTP")
        builder = PlanBuilder(cfg)
        event = _confirmed_event(setup_type="FAILED_LTP", watch_type="FAILED_LTP_WATCH")
        features = _eval_features(close=202.0, open_=200.0, high=203.0, low=199.0)
        plan = builder.build(event, features)
        assert plan.entry_trigger is not None
        assert plan.stop is not None
        assert plan.risk is not None
        assert plan.target_1_5r is not None
        assert plan.reward_risk is not None


# ---------------------------------------------------------------------------
# Rejected setup (REJECTED_SETUP outcome) cannot produce TradePlan
# ---------------------------------------------------------------------------

class TestRejectedSetupCannotProducePlan:
    """REJECTED_SETUP outcome always produces REJECTED_NOT_CONFIRMED.

    This covers WATCH candidates indirectly: all WATCH events (LTP, REJECTION,
    REVERSAL, BOUNCE) currently produce REJECTED_SETUP in Phase 4B because
    level_context and trend_context are unverified.
    """

    def test_rejected_outcome_produces_not_confirmed(self):
        builder = PlanBuilder()
        event = _rejected_confirmation(setup_type="LTP", watch_type="LTP_WATCH")
        features = _eval_features(close=202.0, open_=200.0)
        plan = builder.build(event, features)
        assert plan.plan_status == PlanStatus.REJECTED_NOT_CONFIRMED

    def test_rejected_outcome_is_not_valid(self):
        builder = PlanBuilder()
        event = _rejected_confirmation()
        features = _eval_features(close=202.0, open_=200.0)
        plan = builder.build(event, features)
        assert not plan.is_valid()

    def test_rejected_outcome_has_reason_mentioning_confirmed_setup(self):
        builder = PlanBuilder()
        event = _rejected_confirmation(setup_type="LTP", watch_type="LTP_WATCH")
        features = _eval_features(close=202.0, open_=200.0)
        plan = builder.build(event, features)
        assert "CONFIRMED_SETUP" in plan.rejection_reason

    def test_all_watch_types_produce_not_confirmed(self):
        """All four core KCU WATCH types currently produce REJECTED_SETUP."""
        builder = PlanBuilder()
        features = _eval_features(close=202.0, open_=200.0)
        for setup_type, watch_type in [
            ("LTP", "LTP_WATCH"),
            ("REJECTION", "REJECTION_WATCH"),
            ("REVERSAL", "REVERSAL_WATCH"),
            ("BOUNCE", "BOUNCE_WATCH"),
        ]:
            event = _rejected_confirmation(setup_type=setup_type, watch_type=watch_type)
            plan = builder.build(event, features)
            assert plan.plan_status == PlanStatus.REJECTED_NOT_CONFIRMED, \
                f"Expected REJECTED_NOT_CONFIRMED for {setup_type}"

    def test_rejected_outcome_no_entry_trigger(self):
        builder = PlanBuilder()
        event = _rejected_confirmation()
        features = _eval_features(close=202.0, open_=200.0)
        plan = builder.build(event, features)
        assert plan.entry_trigger is None

    def test_rejected_outcome_no_stop(self):
        builder = PlanBuilder()
        event = _rejected_confirmation()
        features = _eval_features(close=202.0, open_=200.0)
        plan = builder.build(event, features)
        assert plan.stop is None


# ---------------------------------------------------------------------------
# Unsupported (truly unknown) setup type
# ---------------------------------------------------------------------------

class TestUnsupportedSetupType:
    def test_unknown_setup_type_produces_unsupported_type(self):
        builder = PlanBuilder()
        event = _confirmed_event(setup_type="MYSTERY_SETUP", watch_type="MYSTERY_WATCH")
        features = _eval_features(close=202.0, open_=200.0)
        plan = builder.build(event, features)
        assert plan.plan_status == PlanStatus.REJECTED_UNSUPPORTED_TYPE

    def test_unknown_type_rejection_reason_names_it(self):
        builder = PlanBuilder()
        event = _confirmed_event(setup_type="MYSTERY_SETUP", watch_type="MYSTERY_WATCH")
        features = _eval_features(close=202.0, open_=200.0)
        plan = builder.build(event, features)
        assert "MYSTERY_SETUP" in plan.rejection_reason

    def test_known_types_do_not_produce_unsupported_type(self):
        """Known types produce NOT_TRADABLE, not UNSUPPORTED_TYPE."""
        builder = PlanBuilder()
        features = _eval_features(close=202.0, open_=200.0)
        for setup_type in KNOWN_SETUP_TYPES:
            event = _confirmed_event(setup_type=setup_type, watch_type=f"{setup_type}_WATCH")
            plan = builder.build(event, features)
            assert plan.plan_status != PlanStatus.REJECTED_UNSUPPORTED_TYPE, \
                f"Known type {setup_type!r} should not be REJECTED_UNSUPPORTED_TYPE"


# ---------------------------------------------------------------------------
# Non-tradable confirmed setups (known but not in tradable list)
# ---------------------------------------------------------------------------

class TestNonTradableKnownSetups:
    def test_ltp_confirmed_is_not_tradable_by_default(self):
        builder = PlanBuilder()
        event = _confirmed_event(setup_type="LTP", watch_type="LTP_WATCH")
        features = _eval_features(close=202.0, open_=200.0)
        plan = builder.build(event, features)
        assert plan.plan_status == PlanStatus.REJECTED_NOT_TRADABLE

    def test_rejection_confirmed_is_not_tradable_by_default(self):
        builder = PlanBuilder()
        event = _confirmed_event(setup_type="REJECTION", watch_type="REJECTION_WATCH")
        features = _eval_features(close=202.0, open_=200.0)
        plan = builder.build(event, features)
        assert plan.plan_status == PlanStatus.REJECTED_NOT_TRADABLE

    def test_reversal_confirmed_is_not_tradable_by_default(self):
        builder = PlanBuilder()
        event = _confirmed_event(setup_type="REVERSAL", watch_type="REVERSAL_WATCH")
        features = _eval_features(close=202.0, open_=200.0)
        plan = builder.build(event, features)
        assert plan.plan_status == PlanStatus.REJECTED_NOT_TRADABLE

    def test_bounce_confirmed_is_not_tradable_by_default(self):
        builder = PlanBuilder()
        event = _confirmed_event(setup_type="BOUNCE", watch_type="BOUNCE_WATCH")
        features = _eval_features(close=202.0, open_=200.0)
        plan = builder.build(event, features)
        assert plan.plan_status == PlanStatus.REJECTED_NOT_TRADABLE

    def test_ltp_can_be_enabled(self):
        """LTP can be enabled via config once level_context is available."""
        cfg = _enabled_config("LTP")
        builder = PlanBuilder(cfg)
        event = _confirmed_event(setup_type="LTP", watch_type="LTP_WATCH")
        features = _eval_features(close=202.0, open_=200.0, high=203.0, low=199.0)
        plan = builder.build(event, features)
        assert plan.is_valid()

    def test_not_tradable_rejection_reason_mentions_tradable_setup_types(self):
        builder = PlanBuilder()
        event = _confirmed_event(setup_type="LTP", watch_type="LTP_WATCH")
        features = _eval_features(close=202.0, open_=200.0)
        plan = builder.build(event, features)
        assert "tradable_setup_types" in plan.rejection_reason

    def test_not_tradable_has_no_entry_stop_target(self):
        builder = PlanBuilder()
        for setup_type in ("LTP", "REJECTION", "REVERSAL", "BOUNCE", "FAILED_LTP"):
            event = _confirmed_event(setup_type=setup_type, watch_type=f"{setup_type}_WATCH")
            features = _eval_features(close=202.0, open_=200.0)
            plan = builder.build(event, features)
            assert plan.entry_trigger is None, f"{setup_type}: expected no entry_trigger"
            assert plan.stop is None, f"{setup_type}: expected no stop"
            assert plan.target_1_5r is None, f"{setup_type}: expected no target_1_5r"


# ---------------------------------------------------------------------------
# Missing fields → REJECTED_MISSING_FIELDS
# ---------------------------------------------------------------------------

class TestMissingFields:
    def test_doji_candle_unknown_direction_rejects(self):
        cfg = _enabled_config("FAILED_LTP")
        builder = PlanBuilder(cfg)
        event = _confirmed_event(setup_type="FAILED_LTP", watch_type="FAILED_LTP_WATCH")
        features = _eval_features(close=200.0, open_=200.0, high=201.0, low=199.0)
        plan = builder.build(event, features)
        assert plan.plan_status == PlanStatus.REJECTED_MISSING_FIELDS

    def test_doji_rejection_reason_mentions_direction(self):
        cfg = _enabled_config("FAILED_LTP")
        builder = PlanBuilder(cfg)
        event = _confirmed_event(setup_type="FAILED_LTP", watch_type="FAILED_LTP_WATCH")
        features = _eval_features(close=200.0, open_=200.0, high=201.0, low=199.0)
        plan = builder.build(event, features)
        assert "direction" in plan.rejection_reason

    def test_zero_risk_for_long_rejects(self):
        cfg = _enabled_config("FAILED_LTP")
        builder = PlanBuilder(cfg)
        event = _confirmed_event(setup_type="FAILED_LTP", watch_type="FAILED_LTP_WATCH")
        # close > open, but close == low → stop == entry → risk = 0
        features = _eval_features(close=200.0, open_=199.0, high=201.0, low=200.0)
        plan = builder.build(event, features)
        assert plan.plan_status == PlanStatus.REJECTED_MISSING_FIELDS

    def test_zero_risk_for_short_rejects(self):
        cfg = _enabled_config("FAILED_LTP")
        builder = PlanBuilder(cfg)
        event = _confirmed_event(setup_type="FAILED_LTP", watch_type="FAILED_LTP_WATCH")
        # close < open, but close == high → stop == entry for short
        features = _eval_features(close=200.0, open_=201.0, high=200.0, low=199.0)
        plan = builder.build(event, features)
        assert plan.plan_status == PlanStatus.REJECTED_MISSING_FIELDS

    def test_risk_below_min_rejects(self):
        cfg = PlanConfig(tradable_setup_types=frozenset({"FAILED_LTP"}), min_risk_dollars=1.0)
        builder = PlanBuilder(cfg)
        event = _confirmed_event(setup_type="FAILED_LTP", watch_type="FAILED_LTP_WATCH")
        # risk=0.1 < 1.0
        features = _eval_features(close=200.1, open_=200.0, high=201.0, low=200.0)
        plan = builder.build(event, features)
        assert plan.plan_status == PlanStatus.REJECTED_MISSING_FIELDS


# ---------------------------------------------------------------------------
# R:R below minimum
# ---------------------------------------------------------------------------

class TestRRBelowMinimum:
    def test_min_rr_higher_than_target_r_rejects(self):
        cfg = PlanConfig(
            target_r=1.5,
            min_rr_threshold=2.0,
            tradable_setup_types=frozenset({"FAILED_LTP"}),
        )
        builder = PlanBuilder(cfg)
        event = _confirmed_event(setup_type="FAILED_LTP", watch_type="FAILED_LTP_WATCH")
        features = _eval_features(close=202.0, open_=200.0, high=203.0, low=199.0)
        plan = builder.build(event, features)
        assert plan.plan_status == PlanStatus.REJECTED_RR_BELOW_MINIMUM

    def test_min_rr_equal_to_target_r_passes(self):
        cfg = PlanConfig(
            target_r=1.5,
            min_rr_threshold=1.5,
            tradable_setup_types=frozenset({"FAILED_LTP"}),
        )
        builder = PlanBuilder(cfg)
        event = _confirmed_event(setup_type="FAILED_LTP", watch_type="FAILED_LTP_WATCH")
        features = _eval_features(close=202.0, open_=200.0, high=203.0, low=199.0)
        plan = builder.build(event, features)
        assert plan.plan_status == PlanStatus.VALID

    def test_rejection_reason_mentions_rr_values(self):
        cfg = PlanConfig(
            target_r=1.5,
            min_rr_threshold=2.0,
            tradable_setup_types=frozenset({"FAILED_LTP"}),
        )
        builder = PlanBuilder(cfg)
        event = _confirmed_event(setup_type="FAILED_LTP", watch_type="FAILED_LTP_WATCH")
        features = _eval_features(close=202.0, open_=200.0, high=203.0, low=199.0)
        plan = builder.build(event, features)
        assert "1.5" in plan.rejection_reason
        assert "2.0" in plan.rejection_reason


# ---------------------------------------------------------------------------
# target_1_5r calculation correctness
# ---------------------------------------------------------------------------

class TestTarget1_5RCalculation:
    def test_long_target_equals_entry_plus_1_5_times_risk(self):
        cfg = _enabled_config("FAILED_LTP")
        builder = PlanBuilder(cfg)
        event = _confirmed_event(setup_type="FAILED_LTP", watch_type="FAILED_LTP_WATCH")
        features = _eval_features(close=210.0, open_=208.0, high=211.0, low=205.0)
        plan = builder.build(event, features)
        assert plan.entry_trigger == pytest.approx(210.0)
        assert plan.stop == pytest.approx(205.0)
        assert plan.risk == pytest.approx(5.0)
        assert plan.target_1_5r == pytest.approx(217.5)

    def test_short_target_equals_entry_minus_1_5_times_risk(self):
        cfg = _enabled_config("FAILED_LTP")
        builder = PlanBuilder(cfg)
        event = _confirmed_event(setup_type="FAILED_LTP", watch_type="FAILED_LTP_WATCH")
        features = _eval_features(close=205.0, open_=210.0, high=212.0, low=204.0)
        plan = builder.build(event, features)
        assert plan.entry_trigger == pytest.approx(205.0)
        assert plan.stop == pytest.approx(212.0)
        assert plan.risk == pytest.approx(7.0)
        assert plan.target_1_5r == pytest.approx(194.5)

    def test_custom_target_r_is_respected(self):
        cfg = PlanConfig(target_r=2.0, tradable_setup_types=frozenset({"FAILED_LTP"}))
        builder = PlanBuilder(cfg)
        event = _confirmed_event(setup_type="FAILED_LTP", watch_type="FAILED_LTP_WATCH")
        features = _eval_features(close=200.0, open_=198.0, high=201.0, low=196.0)
        plan = builder.build(event, features)
        # entry=200, stop=196, risk=4, target=200+8=208
        assert plan.target_1_5r == pytest.approx(208.0)
        assert plan.reward_risk == pytest.approx(2.0)

    def test_reward_risk_always_equals_target_r(self):
        for target_r in (1.0, 1.5, 2.0, 3.0):
            cfg = PlanConfig(
                target_r=target_r,
                min_rr_threshold=target_r,
                tradable_setup_types=frozenset({"FAILED_LTP"}),
            )
            builder = PlanBuilder(cfg)
            event = _confirmed_event(setup_type="FAILED_LTP", watch_type="FAILED_LTP_WATCH")
            features = _eval_features(close=202.0, open_=200.0, high=203.0, low=199.0)
            plan = builder.build(event, features)
            assert plan.reward_risk == pytest.approx(target_r), \
                f"Expected reward_risk={target_r}, got {plan.reward_risk}"

    def test_target_is_above_entry_for_long(self):
        cfg = _enabled_config("FAILED_LTP")
        builder = PlanBuilder(cfg)
        event = _confirmed_event(setup_type="FAILED_LTP", watch_type="FAILED_LTP_WATCH")
        features = _eval_features(close=202.0, open_=200.0, high=203.0, low=199.0)
        plan = builder.build(event, features)
        assert plan.target_1_5r > plan.entry_trigger

    def test_target_is_below_entry_for_short(self):
        cfg = _enabled_config("FAILED_LTP")
        builder = PlanBuilder(cfg)
        event = _confirmed_event(setup_type="FAILED_LTP", watch_type="FAILED_LTP_WATCH")
        features = _eval_features(close=198.0, open_=200.0, high=201.0, low=197.0)
        plan = builder.build(event, features)
        assert plan.target_1_5r < plan.entry_trigger


# ---------------------------------------------------------------------------
# No future candles
# ---------------------------------------------------------------------------

class TestNoFutureCandles:
    def test_plan_timestamp_comes_from_eval_features(self):
        cfg = _enabled_config("FAILED_LTP")
        builder = PlanBuilder(cfg)
        event = _confirmed_event(evaluated_at_candle_index=11)
        features = _eval_features(close=202.0, open_=200.0, candle_index=11)
        plan = builder.build(event, features)
        assert plan.timestamp == features.timestamp

    def test_plan_candle_index_matches_eval_features(self):
        cfg = _enabled_config("FAILED_LTP")
        builder = PlanBuilder(cfg)
        event = _confirmed_event(evaluated_at_candle_index=15)
        features = _eval_features(close=202.0, open_=200.0, candle_index=15)
        plan = builder.build(event, features)
        assert plan.candle_index == 15

    def test_entry_trigger_is_closed_candle_price(self):
        cfg = _enabled_config("FAILED_LTP")
        builder = PlanBuilder(cfg)
        event = _confirmed_event()
        features = _eval_features(close=202.0, open_=200.0)
        plan = builder.build(event, features)
        assert plan.entry_trigger == features.close

    def test_stop_uses_eval_candle_extreme(self):
        cfg = _enabled_config("FAILED_LTP")
        builder = PlanBuilder(cfg)
        event = _confirmed_event()
        features = _eval_features(close=202.0, open_=200.0, high=203.0, low=199.0)
        plan = builder.build(event, features)
        assert plan.stop == features.low  # long → stop = low (known closed candle)


# ---------------------------------------------------------------------------
# Alignment hardening
# ---------------------------------------------------------------------------

class TestPlanAlignmentHardening:
    def test_mismatched_eval_candle_index_rejected(self):
        builder = PlanBuilder(_enabled_config("FAILED_LTP"))
        event = _confirmed_event(evaluated_at_candle_index=11)
        features = _eval_features(close=202.0, open_=200.0, candle_index=12)
        plan = builder.build(event, features)
        assert plan.plan_status == PlanStatus.REJECTED_EVENT_FEATURE_MISMATCH
        assert "evaluated_at_candle_index" in plan.rejection_reason

    def test_mismatched_symbol_rejected(self):
        builder = PlanBuilder(_enabled_config("FAILED_LTP"))
        event = _confirmed_event()
        features = _eval_features(close=202.0, open_=200.0)
        features = FeatureRecord.from_dict({**features.to_dict(), "symbol": "AAPL"})
        plan = builder.build(event, features)
        assert plan.plan_status == PlanStatus.REJECTED_EVENT_FEATURE_MISMATCH
        assert "event.symbol" in plan.rejection_reason

    def test_mismatched_timeframe_rejected(self):
        builder = PlanBuilder(_enabled_config("FAILED_LTP"))
        event = _confirmed_event()
        features = _eval_features(close=202.0, open_=200.0)
        features = FeatureRecord.from_dict({**features.to_dict(), "timeframe": "5"})
        plan = builder.build(event, features)
        assert plan.plan_status == PlanStatus.REJECTED_EVENT_FEATURE_MISMATCH
        assert "event.timeframe" in plan.rejection_reason

    def test_mismatched_replay_date_rejected(self):
        builder = PlanBuilder(_enabled_config("FAILED_LTP"))
        event = _confirmed_event()
        features = _eval_features(close=202.0, open_=200.0)
        features = FeatureRecord.from_dict({**features.to_dict(), "replay_date": "2024-01-16"})
        plan = builder.build(event, features)
        assert plan.plan_status == PlanStatus.REJECTED_EVENT_FEATURE_MISMATCH
        assert "event.replay_date" in plan.rejection_reason

    def test_multiple_alignment_errors_are_reported_deterministically(self):
        builder = PlanBuilder(_enabled_config("FAILED_LTP"))
        event = _confirmed_event(evaluated_at_candle_index=11)
        features = _eval_features(close=202.0, open_=200.0, candle_index=12)
        features = FeatureRecord.from_dict({
            **features.to_dict(),
            "symbol": "AAPL",
            "timeframe": "5",
            "replay_date": "2024-01-16",
        })
        plan = builder.build(event, features)
        assert plan.plan_status == PlanStatus.REJECTED_EVENT_FEATURE_MISMATCH
        assert "evaluated_at_candle_index" in plan.rejection_reason
        assert "event.symbol" in plan.rejection_reason
        assert "event.timeframe" in plan.rejection_reason
        assert "event.replay_date" in plan.rejection_reason


# ---------------------------------------------------------------------------
# Direction inference helper
# ---------------------------------------------------------------------------

class TestInferDirection:
    def test_close_above_open_is_long(self):
        f = _eval_features(close=202.0, open_=200.0)
        assert _infer_direction(f) == TradePlanDirection.LONG

    def test_close_below_open_is_short(self):
        f = _eval_features(close=198.0, open_=200.0)
        assert _infer_direction(f) == TradePlanDirection.SHORT

    def test_close_equal_open_is_unknown(self):
        f = _eval_features(close=200.0, open_=200.0, high=201.0, low=199.0)
        assert _infer_direction(f) == TradePlanDirection.UNKNOWN


# ---------------------------------------------------------------------------
# Plan ID determinism
# ---------------------------------------------------------------------------

class TestPlanIdDeterminism:
    def test_same_inputs_produce_same_plan_id(self):
        cfg = _enabled_config("FAILED_LTP")
        builder = PlanBuilder(cfg)
        event = _confirmed_event()
        features = _eval_features(close=202.0, open_=200.0)
        assert builder.build(event, features).plan_id == builder.build(event, features).plan_id

    def test_different_candle_index_produces_different_plan_id(self):
        # plan_id uses candidate_candle_index + setup_type — different candidate origins
        # produce different IDs even when evaluated at the same candle.
        cfg = _enabled_config("FAILED_LTP")
        event_a = _confirmed_event(evaluated_at_candle_index=11, candidate_candle_index=9)
        event_b = _confirmed_event(evaluated_at_candle_index=11, candidate_candle_index=10)
        features = _eval_features(close=202.0, open_=200.0, candle_index=11)
        builder = PlanBuilder(cfg)
        assert builder.build(event_a, features).plan_id != builder.build(event_b, features).plan_id


# ---------------------------------------------------------------------------
# Serialisation round-trip
# ---------------------------------------------------------------------------

class TestSerialisationFromBuilder:
    def test_valid_plan_round_trips(self):
        cfg = _enabled_config("FAILED_LTP")
        builder = PlanBuilder(cfg)
        event = _confirmed_event(setup_type="FAILED_LTP", watch_type="FAILED_LTP_WATCH")
        features = _eval_features(close=202.0, open_=200.0, high=203.0, low=199.0)
        plan = builder.build(event, features)
        rebuilt = TradePlan.from_dict(plan.to_dict())
        assert rebuilt.to_dict() == plan.to_dict()

    def test_chop_rejected_plan_round_trips(self):
        builder = PlanBuilder()
        event = _confirmed_event(setup_type="CHOP", watch_type="CHOP")
        features = _eval_features(close=202.0, open_=200.0)
        plan = builder.build(event, features)
        rebuilt = TradePlan.from_dict(plan.to_dict())
        assert rebuilt.plan_status == PlanStatus.REJECTED_NOT_TRADABLE

    def test_not_confirmed_plan_round_trips(self):
        builder = PlanBuilder()
        event = _rejected_confirmation()
        features = _eval_features(close=202.0, open_=200.0)
        plan = builder.build(event, features)
        rebuilt = TradePlan.from_dict(plan.to_dict())
        assert rebuilt.plan_status == PlanStatus.REJECTED_NOT_CONFIRMED


# ---------------------------------------------------------------------------
# Module-level integrity
# ---------------------------------------------------------------------------

class TestModuleIntegrity:
    def test_no_outcome_simulation_terms(self):
        import inspect
        import src.simulator.plan_builder as module
        source = inspect.getsource(module)
        forbidden = ["win_rate", "sharpe", "drawdown", "expectancy", "simulate_outcome"]
        for term in forbidden:
            assert term not in source, f"Found forbidden term {term!r} in plan_builder.py"

    def test_plan_builder_does_not_import_backtest_replay(self):
        import src.simulator.plan_builder as module
        with open(module.__file__) as f:
            source = f.read()
        assert "BacktestReplay" not in source
