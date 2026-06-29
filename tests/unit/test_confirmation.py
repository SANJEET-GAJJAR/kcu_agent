"""Unit tests for Phase 4B — Setup Confirmation Engine.

Proves:
  - Partial LTP (missing level/trend context) cannot confirm.
  - Missing level/trend/PC prevents LTP confirmation.
  - Rejected setups do not become trades (no trade fields).
  - No entry/stop/target/sizing fields anywhere in the output.
  - All ConfirmationEvents pass their own validate().
  - CONFIRMED_SETUP has grade; REJECTED_SETUP does not.
  - FAILED_LTP_WATCH and CHOP can confirm when conditions are met.
  - Decisive directional break invalidates FAILED_LTP_WATCH.
  - Directional expansion invalidates CHOP.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from dataclasses import fields as dc_fields

import pytest

from src.detectors.candidate_event import CandidateEvent
from src.detectors.kcu_candidate_contract import (
    KCUSourceStatus,
    WATCH_CANDIDATE_TYPES,
)
from src.detectors.confirmation_event import (
    ConfirmationEvent,
    ConfirmationOutcome,
    ConfirmationReasonCode,
    SETUP_TYPE_MAP,
    VALID_GRADES,
)
from src.detectors.confirmation_config import ConfirmationConfig
from src.detectors.setup_evaluators import (
    LTPEvaluator,
    RejectionEvaluator,
    ReversalEvaluator,
    BounceEvaluator,
    FailedLTPWatchEvaluator,
    ChopEvaluator,
)
from src.detectors.confirmation_engine import ConfirmationEngine
from src.detectors.detector_engine import DetectorEngine
from src.features.feature_record import FeatureRecord


# ------------------------------------------------------------------
# Test fixtures / helpers
# ------------------------------------------------------------------

TS = 1705329000  # 2024-01-15 09:30


def _feat(
    idx: int = 0,
    ts: int | None = None,
    o: float = 195.0,
    h: float = 197.0,
    l: float = 193.0,
    c: float = 196.0,
    atr: float | None = 2.0,
    body_pct: float | None = 50.0,
    upper_wick: float = 1.0,
    lower_wick: float = 1.0,
    is_hh: bool | None = None,
    is_ll: bool | None = None,
    is_inside: bool | None = None,
    consec_hh: int = 0,
    consec_ll: int = 0,
) -> FeatureRecord:
    rng = h - l
    body = abs(c - o)
    return FeatureRecord(
        timestamp=ts if ts is not None else TS + idx * 120,
        symbol="GENERIC",
        timeframe="2",
        replay_date="2024-01-15",
        candle_index=idx,
        open=o, high=h, low=l, close=c, volume=10000.0,
        candle_body=body,
        upper_wick=upper_wick,
        lower_wick=lower_wick,
        body_pct=body_pct,
        candle_range=rng,
        atr=atr,
        gap_from_prev=None,
        distance_from_prev_close=None,
        is_higher_high=is_hh,
        is_lower_low=is_ll,
        is_inside_bar=is_inside,
        is_outside_bar=None,
        consecutive_hh=consec_hh,
        consecutive_ll=consec_ll,
        consecutive_lh=0,
        consecutive_hl=0,
        relative_volume=None,
        session="regular",
        time_since_open_minutes=0.0,
        distance_from_session_open=0.0,
        indicators={},
    )


def _watch(
    candidate_type: str = "LTP_WATCH",
    source_status: str = KCUSourceStatus.HYPOTHESIS,
    supporting_components: list[str] | None = None,
    required_missing_components: list[str] | None = None,
    supporting_features: dict | None = None,
    idx: int = 0,
    ts: int | None = None,
) -> CandidateEvent:
    defaults: dict[str, list[str]] = {
        "LTP_WATCH": {
            "sc": ["patience_candle"],
            "rm": ["level_context", "trend_context"],
        },
        "REJECTION_WATCH": {
            "sc": ["rejection_wick"],
            "rm": ["level_context", "directional_context"],
        },
        "REVERSAL_WATCH": {
            "sc": ["trend_exhaustion", "change_of_character"],
            "rm": ["level_context"],
        },
        "BOUNCE_WATCH": {
            "sc": ["support_reaction", "directional_wick"],
            "rm": ["level_context"],
        },
        "FAILED_LTP_WATCH": {
            "sc": ["prior_compression", "expansion_failure"],
            "rm": [],
        },
        "CHOP": {
            "sc": ["contained_range"],
            "rm": [],
        },
    }
    d = defaults.get(candidate_type, {"sc": [], "rm": []})
    sc = supporting_components if supporting_components is not None else d["sc"]
    rm = required_missing_components if required_missing_components is not None else d["rm"]

    sf: dict = supporting_features or {}
    if candidate_type == "FAILED_LTP_WATCH" and "current_body_pct" not in sf:
        sf = {"current_body_pct": 20.0, "prior_candle_range": 0.3, **sf}
    if candidate_type == "CHOP" and "chop_trigger" not in sf:
        sf = {"chop_trigger": "inside_bar", **sf}

    return CandidateEvent(
        timestamp=ts if ts is not None else TS + idx * 120,
        symbol="GENERIC",
        timeframe="2",
        replay_date="2024-01-15",
        candle_index=idx,
        candidate_type=candidate_type,
        source_status=source_status,
        reasons=["test reason"],
        reason_codes=["COMPRESSED_RANGE"],
        supporting_features=sf,
        supporting_components=list(sc),
        required_missing_components=list(rm),
        invalidating_components=["range_expansion_below_compression"],
        no_trade_risk=["level_context_unverified"],
    )


_cfg = ConfirmationConfig()


# ------------------------------------------------------------------
# ConfirmationEvent
# ------------------------------------------------------------------

class TestConfirmationEvent:
    def _confirmed(self, **kw) -> ConfirmationEvent:
        base = dict(
            timestamp=TS, symbol="GENERIC", timeframe="2",
            replay_date="2024-01-15", candle_index=0,
            evaluated_at_candle_index=1, evaluated_at_timestamp=TS + 120,
            watch_type="CHOP", setup_type="CHOP",
            outcome=ConfirmationOutcome.CONFIRMED_SETUP,
            grade="B",
            source_status=KCUSourceStatus.CONFIRMED,
            confirmed_components=["contained_range"],
            reasons=["chop confirmed"],
        )
        base.update(kw)
        return ConfirmationEvent(**base)

    def _rejected(self, **kw) -> ConfirmationEvent:
        base = dict(
            timestamp=TS, symbol="GENERIC", timeframe="2",
            replay_date="2024-01-15", candle_index=0,
            evaluated_at_candle_index=0, evaluated_at_timestamp=TS,
            watch_type="LTP_WATCH", setup_type="LTP",
            outcome=ConfirmationOutcome.REJECTED_SETUP,
            grade=None,
            source_status=KCUSourceStatus.HYPOTHESIS,
            confirmed_components=["patience_candle"],
            missing_components=["level_context", "trend_context"],
            reasons=["level unverified"],
        )
        base.update(kw)
        return ConfirmationEvent(**base)

    def test_valid_confirmed_passes(self):
        assert self._confirmed().validate() == []

    def test_valid_rejected_passes(self):
        assert self._rejected().validate() == []

    def test_confirmed_requires_confirmed_status(self):
        e = self._confirmed(source_status=KCUSourceStatus.HYPOTHESIS)
        assert any("source_status" in err for err in e.validate())

    def test_confirmed_requires_grade(self):
        e = self._confirmed(grade=None)
        errors = e.validate()
        assert any("grade" in err for err in errors)

    def test_confirmed_invalid_grade_fails(self):
        e = self._confirmed(grade="X")
        assert any("grade" in err for err in e.validate())

    def test_rejected_must_not_have_grade(self):
        e = self._rejected(grade="B")
        assert any("grade" in err for err in e.validate())

    def test_unknown_outcome_fails(self):
        e = self._rejected(outcome="TRADE_SIGNAL")
        assert any("outcome" in err for err in e.validate())

    def test_empty_reasons_fails(self):
        e = self._confirmed(reasons=[])
        assert any("reasons" in err for err in e.validate())

    def test_all_valid_grades_accepted(self):
        for grade in VALID_GRADES:
            e = self._confirmed(grade=grade)
            assert e.validate() == [], f"grade {grade!r} should be valid"

    def test_to_dict_has_required_keys(self):
        e = self._confirmed()
        d = e.to_dict()
        for key in (
            "timestamp", "symbol", "outcome", "grade", "source_status",
            "watch_type", "setup_type",
            "confirmed_components", "missing_components", "invalidating_components",
            "reasons", "reason_codes",
            "evaluated_at_candle_index", "evaluated_at_timestamp",
            "candidate_candle_index", "candidate_timestamp",
        ):
            assert key in d, f"Missing key: {key}"

    def test_no_entry_stop_target_in_to_dict(self):
        e = self._confirmed()
        d = e.to_dict()
        for term in ("entry", "stop", "target", "sizing", "risk_reward"):
            assert term not in d, f"Trade-management key {term!r} in to_dict()"

    def test_to_jsonl_is_single_line(self):
        e = self._confirmed()
        line = e.to_jsonl_line()
        assert "\n" not in line
        parsed = json.loads(line)
        assert parsed["outcome"] == ConfirmationOutcome.CONFIRMED_SETUP

    def test_roundtrip_from_dict(self):
        e = self._confirmed(
            confirmed_components=["x", "y"],
            grade="A",
        )
        e2 = ConfirmationEvent.from_dict(e.to_dict())
        assert e2.outcome == e.outcome
        assert e2.grade == e.grade
        assert e2.source_status == e.source_status
        assert e2.confirmed_components == e.confirmed_components

    def test_no_entry_stop_target_field_in_dataclass(self):
        field_names = {f.name for f in dc_fields(ConfirmationEvent)}
        for term in ("entry", "stop", "target", "sizing", "risk_reward", "outcome_pnl"):
            assert term not in field_names, (
                f"Trade-management field {term!r} should not exist in ConfirmationEvent"
            )


# ------------------------------------------------------------------
# ConfirmationConfig
# ------------------------------------------------------------------

class TestConfirmationConfig:
    def test_defaults_valid(self):
        cfg = ConfirmationConfig()
        assert cfg.failed_ltp_decisive_body_pct == 60.0
        assert cfg.max_confirmation_wait == 3

    def test_zero_decisive_body_pct_raises(self):
        with pytest.raises(ValueError, match="failed_ltp_decisive_body_pct"):
            ConfirmationConfig(failed_ltp_decisive_body_pct=0.0)

    def test_grade_a_must_be_less_than_grade_b(self):
        with pytest.raises(ValueError, match="grade_a"):
            ConfirmationConfig(
                failed_ltp_grade_a_body_pct=20.0,
                failed_ltp_grade_b_body_pct=10.0,
            )

    def test_max_wait_less_than_one_raises(self):
        with pytest.raises(ValueError, match="max_confirmation_wait"):
            ConfirmationConfig(max_confirmation_wait=0)


# ------------------------------------------------------------------
# Immediate evaluators (always REJECTED in Phase 4B)
# ------------------------------------------------------------------

class TestLTPEvaluator:
    ev = LTPEvaluator()

    def test_always_rejected(self):
        w = _watch("LTP_WATCH", KCUSourceStatus.HYPOTHESIS)
        f = _feat(idx=0)
        ev = self.ev.evaluate_immediate(w, f, _cfg)
        assert ev.outcome == ConfirmationOutcome.REJECTED_SETUP

    def test_source_status_preserved_not_confirmed(self):
        w = _watch("LTP_WATCH", KCUSourceStatus.HYPOTHESIS)
        ev = self.ev.evaluate_immediate(w, _feat(idx=0), _cfg)
        assert ev.source_status == KCUSourceStatus.HYPOTHESIS
        assert ev.source_status != KCUSourceStatus.CONFIRMED

    def test_patience_candle_in_confirmed_components(self):
        w = _watch("LTP_WATCH")
        ev = self.ev.evaluate_immediate(w, _feat(idx=0), _cfg)
        assert "patience_candle" in ev.confirmed_components

    def test_level_context_in_missing_components(self):
        w = _watch("LTP_WATCH")
        ev = self.ev.evaluate_immediate(w, _feat(idx=0), _cfg)
        assert "level_context" in ev.missing_components

    def test_trend_context_in_missing_components(self):
        w = _watch("LTP_WATCH")
        ev = self.ev.evaluate_immediate(w, _feat(idx=0), _cfg)
        assert "trend_context" in ev.missing_components

    def test_reason_code_level_unverified(self):
        w = _watch("LTP_WATCH")
        ev = self.ev.evaluate_immediate(w, _feat(idx=0), _cfg)
        assert ConfirmationReasonCode.LEVEL_CONTEXT_UNVERIFIED in ev.reason_codes

    def test_reason_code_trend_unverified(self):
        w = _watch("LTP_WATCH")
        ev = self.ev.evaluate_immediate(w, _feat(idx=0), _cfg)
        assert ConfirmationReasonCode.TREND_CONTEXT_UNVERIFIED in ev.reason_codes

    def test_no_grade(self):
        w = _watch("LTP_WATCH")
        ev = self.ev.evaluate_immediate(w, _feat(idx=0), _cfg)
        assert ev.grade is None

    def test_partial_ltp_cannot_confirm(self):
        # patience_candle present but level and trend missing → still rejected
        w = _watch("LTP_WATCH", supporting_components=["patience_candle"])
        ev = self.ev.evaluate_immediate(w, _feat(idx=0), _cfg)
        assert ev.outcome == ConfirmationOutcome.REJECTED_SETUP

    def test_watch_type_preserved(self):
        w = _watch("LTP_WATCH")
        ev = self.ev.evaluate_immediate(w, _feat(idx=0), _cfg)
        assert ev.watch_type == "LTP_WATCH"
        assert ev.setup_type == "LTP"

    def test_validation_passes(self):
        w = _watch("LTP_WATCH")
        ev = self.ev.evaluate_immediate(w, _feat(idx=0), _cfg)
        assert ev.validate() == []


class TestRejectionEvaluator:
    ev = RejectionEvaluator()

    def test_always_rejected(self):
        w = _watch("REJECTION_WATCH", KCUSourceStatus.HYPOTHESIS)
        ev = self.ev.evaluate_immediate(w, _feat(idx=0), _cfg)
        assert ev.outcome == ConfirmationOutcome.REJECTED_SETUP

    def test_rejection_wick_in_confirmed(self):
        w = _watch("REJECTION_WATCH")
        ev = self.ev.evaluate_immediate(w, _feat(idx=0), _cfg)
        assert "rejection_wick" in ev.confirmed_components

    def test_level_and_directional_in_missing(self):
        w = _watch("REJECTION_WATCH")
        ev = self.ev.evaluate_immediate(w, _feat(idx=0), _cfg)
        assert "level_context" in ev.missing_components
        assert "directional_context" in ev.missing_components

    def test_reason_codes_level_and_directional(self):
        w = _watch("REJECTION_WATCH")
        ev = self.ev.evaluate_immediate(w, _feat(idx=0), _cfg)
        assert ConfirmationReasonCode.LEVEL_CONTEXT_UNVERIFIED in ev.reason_codes
        assert ConfirmationReasonCode.DIRECTIONAL_CONTEXT_UNVERIFIED in ev.reason_codes

    def test_validation_passes(self):
        w = _watch("REJECTION_WATCH")
        ev = self.ev.evaluate_immediate(w, _feat(idx=0), _cfg)
        assert ev.validate() == []

    def test_missing_level_prevents_rejection_confirmation(self):
        # Even if rejection_wick is strong, without level_context: rejected
        w = _watch("REJECTION_WATCH",
                   supporting_components=["rejection_wick"],
                   required_missing_components=["level_context", "directional_context"])
        ev = self.ev.evaluate_immediate(w, _feat(idx=0), _cfg)
        assert ev.outcome == ConfirmationOutcome.REJECTED_SETUP


class TestReversalEvaluator:
    ev = ReversalEvaluator()

    def test_always_rejected(self):
        w = _watch("REVERSAL_WATCH", KCUSourceStatus.PARTIALLY_COVERED)
        ev = self.ev.evaluate_immediate(w, _feat(idx=0), _cfg)
        assert ev.outcome == ConfirmationOutcome.REJECTED_SETUP

    def test_two_components_in_confirmed(self):
        w = _watch("REVERSAL_WATCH")
        ev = self.ev.evaluate_immediate(w, _feat(idx=0), _cfg)
        assert "trend_exhaustion" in ev.confirmed_components
        assert "change_of_character" in ev.confirmed_components

    def test_level_context_in_missing(self):
        w = _watch("REVERSAL_WATCH")
        ev = self.ev.evaluate_immediate(w, _feat(idx=0), _cfg)
        assert "level_context" in ev.missing_components

    def test_reason_code_level_unverified(self):
        w = _watch("REVERSAL_WATCH")
        ev = self.ev.evaluate_immediate(w, _feat(idx=0), _cfg)
        assert ConfirmationReasonCode.LEVEL_CONTEXT_UNVERIFIED in ev.reason_codes

    def test_validation_passes(self):
        w = _watch("REVERSAL_WATCH")
        ev = self.ev.evaluate_immediate(w, _feat(idx=0), _cfg)
        assert ev.validate() == []

    def test_missing_level_prevents_reversal_confirmation(self):
        w = _watch("REVERSAL_WATCH",
                   supporting_components=["trend_exhaustion", "change_of_character"],
                   required_missing_components=["level_context"])
        ev = self.ev.evaluate_immediate(w, _feat(idx=0), _cfg)
        assert ev.outcome == ConfirmationOutcome.REJECTED_SETUP


class TestBounceEvaluator:
    ev = BounceEvaluator()

    def test_always_rejected(self):
        w = _watch("BOUNCE_WATCH", KCUSourceStatus.PARTIALLY_COVERED)
        ev = self.ev.evaluate_immediate(w, _feat(idx=0), _cfg)
        assert ev.outcome == ConfirmationOutcome.REJECTED_SETUP

    def test_two_components_in_confirmed(self):
        w = _watch("BOUNCE_WATCH")
        ev = self.ev.evaluate_immediate(w, _feat(idx=0), _cfg)
        assert "support_reaction" in ev.confirmed_components
        assert "directional_wick" in ev.confirmed_components

    def test_level_context_in_missing(self):
        w = _watch("BOUNCE_WATCH")
        ev = self.ev.evaluate_immediate(w, _feat(idx=0), _cfg)
        assert "level_context" in ev.missing_components

    def test_validation_passes(self):
        w = _watch("BOUNCE_WATCH")
        ev = self.ev.evaluate_immediate(w, _feat(idx=0), _cfg)
        assert ev.validate() == []

    def test_missing_level_prevents_bounce_confirmation(self):
        w = _watch("BOUNCE_WATCH",
                   supporting_components=["support_reaction", "directional_wick"],
                   required_missing_components=["level_context"])
        ev = self.ev.evaluate_immediate(w, _feat(idx=0), _cfg)
        assert ev.outcome == ConfirmationOutcome.REJECTED_SETUP


# ------------------------------------------------------------------
# Deferred evaluator: FailedLTPWatchEvaluator
# ------------------------------------------------------------------

class TestFailedLTPWatchEvaluator:
    ev = FailedLTPWatchEvaluator()

    def _candidate(self, body_pct: float | None = 20.0) -> CandidateEvent:
        sf = {"current_body_pct": body_pct} if body_pct is not None else {}
        sf["prior_candle_range"] = 0.3
        return _watch("FAILED_LTP_WATCH",
                      KCUSourceStatus.PARTIALLY_COVERED,
                      supporting_features=sf,
                      idx=5)

    def test_confirmed_when_no_decisive_break(self):
        w = self._candidate(body_pct=20.0)
        next_f = _feat(idx=6, body_pct=20.0, is_hh=False, is_ll=False)
        ev = self.ev.evaluate_deferred(w, next_f, _cfg)
        assert ev.outcome == ConfirmationOutcome.CONFIRMED_SETUP

    def test_rejected_when_decisive_break_higher_high(self):
        w = self._candidate(body_pct=20.0)
        # body_pct >= 60 AND is_higher_high → decisive directional break
        next_f = _feat(idx=6, body_pct=70.0, is_hh=True, is_ll=False)
        ev = self.ev.evaluate_deferred(w, next_f, _cfg)
        assert ev.outcome == ConfirmationOutcome.REJECTED_SETUP

    def test_rejected_when_decisive_break_lower_low(self):
        w = self._candidate(body_pct=20.0)
        next_f = _feat(idx=6, body_pct=70.0, is_hh=False, is_ll=True)
        ev = self.ev.evaluate_deferred(w, next_f, _cfg)
        assert ev.outcome == ConfirmationOutcome.REJECTED_SETUP

    def test_not_rejected_if_body_decisive_but_no_structural_break(self):
        # Large body but no new HH or LL — still confirms
        w = self._candidate(body_pct=20.0)
        next_f = _feat(idx=6, body_pct=70.0, is_hh=False, is_ll=False)
        ev = self.ev.evaluate_deferred(w, next_f, _cfg)
        assert ev.outcome == ConfirmationOutcome.CONFIRMED_SETUP

    def test_not_rejected_if_hh_but_body_not_decisive(self):
        # New HH but body_pct below threshold — still confirms
        w = self._candidate(body_pct=20.0)
        next_f = _feat(idx=6, body_pct=40.0, is_hh=True, is_ll=False)
        ev = self.ev.evaluate_deferred(w, next_f, _cfg)
        assert ev.outcome == ConfirmationOutcome.CONFIRMED_SETUP

    def test_confirmed_has_source_status_confirmed(self):
        w = self._candidate(body_pct=5.0)
        next_f = _feat(idx=6, body_pct=10.0, is_hh=False, is_ll=False)
        ev = self.ev.evaluate_deferred(w, next_f, _cfg)
        assert ev.source_status == KCUSourceStatus.CONFIRMED

    def test_confirmed_has_grade(self):
        w = self._candidate(body_pct=5.0)
        next_f = _feat(idx=6, body_pct=5.0, is_hh=False, is_ll=False)
        ev = self.ev.evaluate_deferred(w, next_f, _cfg)
        assert ev.grade in VALID_GRADES

    def test_grade_a_for_very_indecisive(self):
        cfg = ConfirmationConfig(failed_ltp_grade_a_body_pct=10.0, failed_ltp_grade_b_body_pct=20.0)
        w = self._candidate(body_pct=5.0)
        next_f = _feat(idx=6, body_pct=5.0, is_hh=False, is_ll=False)
        ev = self.ev.evaluate_deferred(w, next_f, cfg)
        assert ev.grade == "A"

    def test_grade_b_for_moderate_indecision(self):
        cfg = ConfirmationConfig(failed_ltp_grade_a_body_pct=10.0, failed_ltp_grade_b_body_pct=20.0)
        w = self._candidate(body_pct=15.0)
        next_f = _feat(idx=6, body_pct=15.0, is_hh=False, is_ll=False)
        ev = self.ev.evaluate_deferred(w, next_f, cfg)
        assert ev.grade == "B"

    def test_grade_c_for_borderline(self):
        cfg = ConfirmationConfig(failed_ltp_grade_a_body_pct=10.0, failed_ltp_grade_b_body_pct=20.0)
        w = self._candidate(body_pct=25.0)
        next_f = _feat(idx=6, body_pct=25.0, is_hh=False, is_ll=False)
        ev = self.ev.evaluate_deferred(w, next_f, cfg)
        assert ev.grade == "C"

    def test_grade_a_for_doji_body(self):
        w = _watch("FAILED_LTP_WATCH",
                   supporting_features={"current_body_pct": None},
                   idx=5)
        next_f = _feat(idx=6, body_pct=5.0, is_hh=False, is_ll=False)
        ev = self.ev.evaluate_deferred(w, next_f, _cfg)
        assert ev.grade == "A"

    def test_rejected_has_no_grade(self):
        w = self._candidate(body_pct=20.0)
        next_f = _feat(idx=6, body_pct=70.0, is_hh=True, is_ll=False)
        ev = self.ev.evaluate_deferred(w, next_f, _cfg)
        assert ev.grade is None

    def test_decisive_break_in_invalidating_components(self):
        w = self._candidate()
        next_f = _feat(idx=6, body_pct=70.0, is_hh=True, is_ll=False)
        ev = self.ev.evaluate_deferred(w, next_f, _cfg)
        assert "decisive_directional_break" in ev.invalidating_components

    def test_force_reject(self):
        w = self._candidate()
        f = _feat(idx=10)
        ev = self.ev.force_reject(w, f)
        assert ev.outcome == ConfirmationOutcome.REJECTED_SETUP
        assert ConfirmationReasonCode.CONFIRMATION_WINDOW_EXPIRED in ev.reason_codes

    def test_confirmation_validation_passes(self):
        w = self._candidate(body_pct=5.0)
        next_f = _feat(idx=6, body_pct=5.0, is_hh=False, is_ll=False)
        ev = self.ev.evaluate_deferred(w, next_f, _cfg)
        assert ev.validate() == []

    def test_rejection_validation_passes(self):
        w = self._candidate()
        next_f = _feat(idx=6, body_pct=75.0, is_hh=True, is_ll=False)
        ev = self.ev.evaluate_deferred(w, next_f, _cfg)
        assert ev.validate() == []


# ------------------------------------------------------------------
# Deferred evaluator: ChopEvaluator
# ------------------------------------------------------------------

class TestChopEvaluator:
    ev = ChopEvaluator()

    def _candidate(self, trigger: str = "inside_bar") -> CandidateEvent:
        return _watch("CHOP",
                      KCUSourceStatus.PARTIALLY_COVERED,
                      supporting_features={"chop_trigger": trigger},
                      idx=3)

    def test_confirmed_when_no_expansion(self):
        w = self._candidate("inside_bar")
        next_f = _feat(idx=4, is_hh=False, is_ll=False, is_inside=True)
        ev = self.ev.evaluate_deferred(w, next_f, _cfg)
        assert ev.outcome == ConfirmationOutcome.CONFIRMED_SETUP

    def test_rejected_when_higher_high(self):
        w = self._candidate("structural")
        next_f = _feat(idx=4, is_hh=True, is_ll=False)
        ev = self.ev.evaluate_deferred(w, next_f, _cfg)
        assert ev.outcome == ConfirmationOutcome.REJECTED_SETUP

    def test_rejected_when_lower_low(self):
        w = self._candidate("inside_bar")
        next_f = _feat(idx=4, is_hh=False, is_ll=True)
        ev = self.ev.evaluate_deferred(w, next_f, _cfg)
        assert ev.outcome == ConfirmationOutcome.REJECTED_SETUP

    def test_expansion_in_invalidating_components(self):
        w = self._candidate()
        next_f = _feat(idx=4, is_hh=True, is_ll=False)
        ev = self.ev.evaluate_deferred(w, next_f, _cfg)
        assert "directional_range_expansion" in ev.invalidating_components

    def test_inside_bar_trigger_grade_a(self):
        w = self._candidate("inside_bar")
        next_f = _feat(idx=4, is_hh=False, is_ll=False)
        ev = self.ev.evaluate_deferred(w, next_f, _cfg)
        assert ev.grade == "A"

    def test_both_trigger_grade_a(self):
        w = self._candidate("both")
        next_f = _feat(idx=4, is_hh=False, is_ll=False)
        ev = self.ev.evaluate_deferred(w, next_f, _cfg)
        assert ev.grade == "A"

    def test_structural_trigger_grade_b(self):
        w = self._candidate("structural")
        next_f = _feat(idx=4, is_hh=False, is_ll=False)
        ev = self.ev.evaluate_deferred(w, next_f, _cfg)
        assert ev.grade == "B"

    def test_confirmed_has_source_status_confirmed(self):
        w = self._candidate()
        next_f = _feat(idx=4, is_hh=False, is_ll=False)
        ev = self.ev.evaluate_deferred(w, next_f, _cfg)
        assert ev.source_status == KCUSourceStatus.CONFIRMED

    def test_rejected_has_no_grade(self):
        w = self._candidate()
        next_f = _feat(idx=4, is_hh=True, is_ll=False)
        ev = self.ev.evaluate_deferred(w, next_f, _cfg)
        assert ev.grade is None

    def test_force_reject(self):
        w = self._candidate()
        ev = self.ev.force_reject(w, _feat(idx=10))
        assert ev.outcome == ConfirmationOutcome.REJECTED_SETUP
        assert ConfirmationReasonCode.CONFIRMATION_WINDOW_EXPIRED in ev.reason_codes

    def test_confirmation_validation_passes(self):
        w = self._candidate()
        next_f = _feat(idx=4, is_hh=False, is_ll=False)
        ev = self.ev.evaluate_deferred(w, next_f, _cfg)
        assert ev.validate() == []

    def test_rejection_validation_passes(self):
        w = self._candidate()
        next_f = _feat(idx=4, is_hh=True, is_ll=False)
        ev = self.ev.evaluate_deferred(w, next_f, _cfg)
        assert ev.validate() == []


# ------------------------------------------------------------------
# ConfirmationEngine
# ------------------------------------------------------------------

class TestConfirmationEngine:
    def test_ltp_watch_immediately_rejected(self):
        engine = ConfirmationEngine()
        f = _feat(idx=0)
        evs = engine.step([_watch("LTP_WATCH", idx=0)], f)
        assert len(evs) == 1
        assert evs[0].outcome == ConfirmationOutcome.REJECTED_SETUP
        assert evs[0].watch_type == "LTP_WATCH"

    def test_rejection_watch_immediately_rejected(self):
        engine = ConfirmationEngine()
        evs = engine.step([_watch("REJECTION_WATCH", idx=0)], _feat(idx=0))
        assert evs[0].outcome == ConfirmationOutcome.REJECTED_SETUP

    def test_reversal_watch_immediately_rejected(self):
        engine = ConfirmationEngine()
        evs = engine.step([_watch("REVERSAL_WATCH", idx=0,
                                  source_status=KCUSourceStatus.PARTIALLY_COVERED)], _feat(idx=0))
        assert evs[0].outcome == ConfirmationOutcome.REJECTED_SETUP

    def test_bounce_watch_immediately_rejected(self):
        engine = ConfirmationEngine()
        evs = engine.step([_watch("BOUNCE_WATCH", idx=0,
                                  source_status=KCUSourceStatus.PARTIALLY_COVERED)], _feat(idx=0))
        assert evs[0].outcome == ConfirmationOutcome.REJECTED_SETUP

    def test_failed_ltp_watch_deferred_to_next_candle(self):
        engine = ConfirmationEngine()
        # Candle 5: FAILED_LTP_WATCH fired → no immediate output
        evs_5 = engine.step([_watch("FAILED_LTP_WATCH",
                                    KCUSourceStatus.PARTIALLY_COVERED, idx=5)], _feat(idx=5))
        assert evs_5 == []
        assert engine.pending_count == 1

        # Candle 6: pending evaluated → output
        evs_6 = engine.step([], _feat(idx=6, body_pct=20.0, is_hh=False, is_ll=False))
        assert len(evs_6) == 1
        assert engine.pending_count == 0

    def test_failed_ltp_watch_confirmed_at_next_candle(self):
        engine = ConfirmationEngine()
        engine.step([_watch("FAILED_LTP_WATCH", KCUSourceStatus.PARTIALLY_COVERED, idx=5)],
                    _feat(idx=5))
        evs = engine.step([], _feat(idx=6, body_pct=15.0, is_hh=False, is_ll=False))
        assert evs[0].outcome == ConfirmationOutcome.CONFIRMED_SETUP

    def test_failed_ltp_watch_rejected_by_decisive_break(self):
        engine = ConfirmationEngine()
        engine.step([_watch("FAILED_LTP_WATCH", KCUSourceStatus.PARTIALLY_COVERED, idx=5)],
                    _feat(idx=5))
        evs = engine.step([], _feat(idx=6, body_pct=70.0, is_hh=True, is_ll=False))
        assert evs[0].outcome == ConfirmationOutcome.REJECTED_SETUP

    def test_chop_deferred_to_next_candle(self):
        engine = ConfirmationEngine()
        evs_3 = engine.step([_watch("CHOP", KCUSourceStatus.PARTIALLY_COVERED, idx=3)],
                             _feat(idx=3))
        assert evs_3 == []
        assert engine.pending_count == 1

        evs_4 = engine.step([], _feat(idx=4, is_hh=False, is_ll=False, is_inside=True))
        assert len(evs_4) == 1
        assert engine.pending_count == 0

    def test_chop_confirmed_when_no_expansion(self):
        engine = ConfirmationEngine()
        engine.step([_watch("CHOP", KCUSourceStatus.PARTIALLY_COVERED, idx=3)], _feat(idx=3))
        evs = engine.step([], _feat(idx=4, is_hh=False, is_ll=False))
        assert evs[0].outcome == ConfirmationOutcome.CONFIRMED_SETUP

    def test_chop_rejected_on_expansion(self):
        engine = ConfirmationEngine()
        engine.step([_watch("CHOP", KCUSourceStatus.PARTIALLY_COVERED, idx=3)], _feat(idx=3))
        evs = engine.step([], _feat(idx=4, is_hh=True, is_ll=False))
        assert evs[0].outcome == ConfirmationOutcome.REJECTED_SETUP

    def test_flush_force_rejects_pending(self):
        engine = ConfirmationEngine()
        engine.step([_watch("CHOP", KCUSourceStatus.PARTIALLY_COVERED, idx=5)], _feat(idx=5))
        assert engine.pending_count == 1
        flushed = engine.flush(_feat(idx=5))
        assert len(flushed) == 1
        assert flushed[0].outcome == ConfirmationOutcome.REJECTED_SETUP
        assert engine.pending_count == 0

    def test_reset_clears_pending(self):
        engine = ConfirmationEngine()
        engine.step([_watch("CHOP", KCUSourceStatus.PARTIALLY_COVERED, idx=3)], _feat(idx=3))
        assert engine.pending_count == 1
        engine.reset()
        assert engine.pending_count == 0

    def test_all_events_pass_validation(self):
        engine = ConfirmationEngine()
        candidates = [
            _watch("LTP_WATCH", idx=0),
            _watch("REJECTION_WATCH", idx=0),
            _watch("REVERSAL_WATCH", KCUSourceStatus.PARTIALLY_COVERED, idx=0),
            _watch("BOUNCE_WATCH", KCUSourceStatus.PARTIALLY_COVERED, idx=0),
            _watch("FAILED_LTP_WATCH", KCUSourceStatus.PARTIALLY_COVERED, idx=0),
            _watch("CHOP", KCUSourceStatus.PARTIALLY_COVERED, idx=0),
        ]
        evs_0 = engine.step(candidates, _feat(idx=0))
        evs_1 = engine.step([], _feat(idx=1, body_pct=20.0, is_hh=False, is_ll=False))
        all_evs = evs_0 + evs_1 + engine.flush(_feat(idx=1))
        for ev in all_evs:
            assert ev.validate() == [], f"Invalid: {ev.outcome} {ev.watch_type}: {ev.validate()}"

    def test_run_equal_to_step_plus_flush(self):
        records = [_feat(idx=i) for i in range(5)]
        candidates_per_candle = [
            [_watch("CHOP", KCUSourceStatus.PARTIALLY_COVERED, idx=i)] for i in range(5)
        ]
        engine_a = ConfirmationEngine()
        result_a = engine_a.run(records, candidates_per_candle)

        engine_b = ConfirmationEngine()
        result_b = []
        for rec, cands in zip(records, candidates_per_candle):
            result_b.extend(engine_b.step(cands, rec))
        result_b.extend(engine_b.flush(records[-1]))

        assert [e.to_dict() for e in result_a] == [e.to_dict() for e in result_b]

    def test_run_mismatched_lengths_raises(self):
        engine = ConfirmationEngine()
        with pytest.raises(ValueError, match="equal length"):
            engine.run([_feat(idx=0)], [[], []])

    def test_deterministic(self):
        records = [_feat(idx=i) for i in range(6)]
        cands = [
            [_watch("CHOP", KCUSourceStatus.PARTIALLY_COVERED, idx=i)] for i in range(6)
        ]
        r1 = ConfirmationEngine().run(records, cands)
        r2 = ConfirmationEngine().run(records, cands)
        assert [e.to_dict() for e in r1] == [e.to_dict() for e in r2]

    def test_events_chronological(self):
        records = [_feat(idx=i) for i in range(8)]
        cands = [[_watch("LTP_WATCH", idx=i)] if i % 2 == 0 else [] for i in range(8)]
        evs = ConfirmationEngine().run(records, cands)
        ts_list = [e.evaluated_at_candle_index for e in evs]
        assert ts_list == sorted(ts_list)

    def test_no_lookahead_pending_evaluated_one_candle_later(self):
        engine = ConfirmationEngine()
        f0 = _feat(idx=0)
        f1 = _feat(idx=1, is_hh=False, is_ll=False)
        chop = _watch("CHOP", KCUSourceStatus.PARTIALLY_COVERED, idx=0)
        evs_0 = engine.step([chop], f0)
        # At candle 0 — deferred, no events yet
        assert evs_0 == []
        # At candle 1 — pending evaluated using candle 1 features (not candle 0)
        evs_1 = engine.step([], f1)
        assert len(evs_1) == 1
        assert evs_1[0].evaluated_at_candle_index == 1
        assert evs_1[0].candle_index == 0   # origin was candle 0


# ------------------------------------------------------------------
# Integration: DetectorEngine → ConfirmationEngine
# ------------------------------------------------------------------

class TestIntegration:
    def test_ltp_watch_pipeline_to_rejection(self):
        """Compressed candle → LTP_WATCH → REJECTED_SETUP (level unverified)."""
        det_engine = DetectorEngine.default()
        conf_engine = ConfirmationEngine()

        records = [
            _feat(idx=0),
            _feat(idx=1, h=195.3, l=194.7, atr=2.0, body_pct=30.0,
                  upper_wick=0.15, lower_wick=0.15),
        ]

        all_conf_events = []
        for rec in records:
            watches = det_engine.process(rec)
            conf_evs = conf_engine.step(watches, rec)
            all_conf_events.extend(conf_evs)
        all_conf_events.extend(conf_engine.flush(records[-1]))

        ltp_rejects = [
            e for e in all_conf_events
            if e.watch_type == "LTP_WATCH" and e.outcome == ConfirmationOutcome.REJECTED_SETUP
        ]
        assert len(ltp_rejects) > 0

    def test_chop_pipeline_to_confirmation(self):
        """Inside bar → CHOP → CONFIRMED_SETUP (no expansion at N+1)."""
        det_engine = DetectorEngine.default()
        conf_engine = ConfirmationEngine()

        records = [
            _feat(idx=0, h=197.0, l=193.0),
            _feat(idx=1, h=196.0, l=194.0, is_hh=False, is_ll=False,
                  is_inside=True, body_pct=20.0),
            # N+1: no new extreme → CHOP confirms
            _feat(idx=2, h=195.5, l=194.5, is_hh=False, is_ll=False,
                  is_inside=False, body_pct=30.0),
        ]

        all_conf_events = []
        for rec in records:
            watches = det_engine.process(rec)
            conf_evs = conf_engine.step(watches, rec)
            all_conf_events.extend(conf_evs)
        all_conf_events.extend(conf_engine.flush(records[-1]))

        chop_confirms = [
            e for e in all_conf_events
            if e.watch_type == "CHOP" and e.outcome == ConfirmationOutcome.CONFIRMED_SETUP
        ]
        assert len(chop_confirms) > 0
        assert all(e.grade in VALID_GRADES for e in chop_confirms)

    def test_all_pipeline_events_pass_validation(self):
        det_engine = DetectorEngine.default()
        conf_engine = ConfirmationEngine()

        records = [
            _feat(idx=i,
                  h=197.0 + (i % 3) * 0.4,
                  l=193.0 - (i % 2) * 0.2,
                  is_hh=bool(i % 2),
                  is_ll=bool((i + 1) % 3),
                  is_inside=bool(i % 5 == 0),
                  atr=2.0,
                  body_pct=float((i * 17) % 90))
            for i in range(10)
        ]

        all_conf = []
        for rec in records:
            watches = det_engine.process(rec)
            all_conf.extend(conf_engine.step(watches, rec))
        all_conf.extend(conf_engine.flush(records[-1]))

        for ev in all_conf:
            errs = ev.validate()
            assert errs == [], f"{ev.watch_type} {ev.outcome}: {errs}"


# ------------------------------------------------------------------
# KCU Phase 4B Audit
# ------------------------------------------------------------------

class TestKCUPhase4BAudit:
    """Proves core Phase 4B guarantees."""

    def _run_all(self) -> list[ConfirmationEvent]:
        det = DetectorEngine.default()
        conf = ConfirmationEngine()
        records = [
            _feat(idx=i,
                  h=197.0 + (i % 5) * 0.3,
                  l=193.0 - (i % 4) * 0.2,
                  o=195.0 + (i % 3) * 0.1,
                  c=195.5 + (i % 6) * 0.12,
                  atr=2.0,
                  body_pct=float((i * 13) % 85),
                  upper_wick=0.4 + (i % 4) * 0.2,
                  lower_wick=0.3 + (i % 3) * 0.2,
                  is_hh=bool(i % 2),
                  is_ll=bool((i + 1) % 3),
                  is_inside=bool(i % 5 == 0),
                  consec_hh=i % 4,
                  consec_ll=i % 3)
            for i in range(30)
        ]
        all_evs = []
        for rec in records:
            watches = det.process(rec)
            all_evs.extend(conf.step(watches, rec))
        all_evs.extend(conf.flush(records[-1]))
        return all_evs

    def test_no_confirmed_setup_for_ltp_watch(self):
        for ev in self._run_all():
            if ev.watch_type == "LTP_WATCH":
                assert ev.outcome == ConfirmationOutcome.REJECTED_SETUP, (
                    f"LTP_WATCH produced CONFIRMED_SETUP at candle {ev.candle_index}"
                )

    def test_no_confirmed_setup_for_rejection_watch(self):
        for ev in self._run_all():
            if ev.watch_type == "REJECTION_WATCH":
                assert ev.outcome == ConfirmationOutcome.REJECTED_SETUP

    def test_no_confirmed_setup_for_reversal_watch(self):
        for ev in self._run_all():
            if ev.watch_type == "REVERSAL_WATCH":
                assert ev.outcome == ConfirmationOutcome.REJECTED_SETUP

    def test_no_confirmed_setup_for_bounce_watch(self):
        for ev in self._run_all():
            if ev.watch_type == "BOUNCE_WATCH":
                assert ev.outcome == ConfirmationOutcome.REJECTED_SETUP

    def test_missing_level_context_prevents_confirmation(self):
        evs = self._run_all()
        for ev in evs:
            if "level_context" in ev.missing_components:
                assert ev.outcome == ConfirmationOutcome.REJECTED_SETUP, (
                    f"{ev.watch_type} confirmed despite missing level_context"
                )

    def test_missing_trend_context_prevents_ltp_confirmation(self):
        evs = self._run_all()
        for ev in evs:
            if ev.watch_type == "LTP_WATCH":
                assert "trend_context" in ev.missing_components
                assert ev.outcome == ConfirmationOutcome.REJECTED_SETUP

    def test_rejected_setups_do_not_have_trade_fields(self):
        field_names = {f.name for f in dc_fields(ConfirmationEvent)}
        forbidden = {"entry", "stop", "target", "stop_loss", "take_profit", "sizing"}
        for term in forbidden:
            assert term not in field_names, (
                f"Trade field {term!r} must not exist in ConfirmationEvent"
            )

    def test_confirmed_setups_have_grade(self):
        for ev in self._run_all():
            if ev.outcome == ConfirmationOutcome.CONFIRMED_SETUP:
                assert ev.grade in VALID_GRADES, (
                    f"CONFIRMED_SETUP has invalid grade: {ev.grade!r}"
                )

    def test_rejected_setups_have_no_grade(self):
        for ev in self._run_all():
            if ev.outcome == ConfirmationOutcome.REJECTED_SETUP:
                assert ev.grade is None, (
                    f"REJECTED_SETUP should have grade=None, got {ev.grade!r}"
                )

    def test_confirmed_setups_have_confirmed_status(self):
        for ev in self._run_all():
            if ev.outcome == ConfirmationOutcome.CONFIRMED_SETUP:
                assert ev.source_status == KCUSourceStatus.CONFIRMED

    def test_rejected_setups_never_have_confirmed_status(self):
        for ev in self._run_all():
            if ev.outcome == ConfirmationOutcome.REJECTED_SETUP:
                assert ev.source_status != KCUSourceStatus.CONFIRMED

    def test_all_confirmation_events_pass_validation(self):
        for ev in self._run_all():
            errs = ev.validate()
            assert errs == [], (
                f"{ev.watch_type} {ev.outcome} at candle {ev.candle_index}: {errs}"
            )

    def test_reason_codes_are_stable_identifiers(self):
        import re
        pattern = re.compile(r'^[A-Z][A-Z0-9_]+$')
        for ev in self._run_all():
            for code in ev.reason_codes:
                assert pattern.match(code), (
                    f"reason_code {code!r} is not a stable uppercase identifier"
                )


# ------------------------------------------------------------------
# Source-level trade management scan
# ------------------------------------------------------------------

CONFIRMATION_MODULES = [
    "src.detectors.confirmation_event",
    "src.detectors.confirmation_config",
    "src.detectors.setup_evaluators",
    "src.detectors.confirmation_engine",
]

FORBIDDEN_TERMS = [
    "stop_loss", "take_profit", "position_size", "risk_reward",
    "win_rate", "win rate", "probability", "edge_score",
    "setup_grade_implies_trade", "buy signal", "sell signal",
    "entry_price", "exit_price",
]


class TestNoTradeManagementInSource:
    @pytest.mark.parametrize("module_path", CONFIRMATION_MODULES)
    def test_no_trade_terms(self, module_path):
        import importlib
        import inspect
        mod = importlib.import_module(module_path)
        src = inspect.getsource(mod).lower()
        for term in FORBIDDEN_TERMS:
            assert term not in src, (
                f"Forbidden term {term!r} found in {module_path}"
            )


class TestNoLookaheadInConfirmation:
    def test_pending_not_evaluated_same_candle(self):
        engine = ConfirmationEngine()
        f0 = _feat(idx=0)
        chop = _watch("CHOP", KCUSourceStatus.PARTIALLY_COVERED, idx=0)
        evs = engine.step([chop], f0)
        assert evs == [], (
            "CHOP candidate should not produce output on the same candle"
        )
        assert engine.pending_count == 1

    def test_deferred_evaluation_uses_next_candle_index(self):
        engine = ConfirmationEngine()
        engine.step(
            [_watch("FAILED_LTP_WATCH", KCUSourceStatus.PARTIALLY_COVERED, idx=7)],
            _feat(idx=7),
        )
        evs = engine.step([], _feat(idx=8, body_pct=15.0, is_hh=False, is_ll=False))
        assert evs[0].evaluated_at_candle_index == 8

    def test_no_confirmation_module_imports_replay_engine(self):
        pkg_path = Path(__file__).parents[2] / "src" / "detectors"
        confirmation_files = [
            "confirmation_event.py",
            "confirmation_config.py",
            "setup_evaluators.py",
            "confirmation_engine.py",
        ]
        for fname in confirmation_files:
            fpath = pkg_path / fname
            tree = ast.parse(fpath.read_text())
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    module = getattr(node, "module", "") or ""
                    names = [a.name for a in getattr(node, "names", [])]
                    for ref in [module] + names:
                        assert "replay_engine" not in ref.lower(), (
                            f"{fname} imports replay_engine: {ref}"
                        )
