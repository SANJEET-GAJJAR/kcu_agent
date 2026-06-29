"""Unit tests for Phase 4A — KCU-audited Setup Candidate Detection Engine.

All tests are independent of TradingView. No mocks of external systems.
Detectors are tested with crafted FeatureRecords.
KCU audit tests assert that no detector claims setup validity.
"""
from __future__ import annotations

import ast
import json
import pytest
from pathlib import Path
from typing import Any

from src.detectors.candidate_event import CandidateEvent
from src.detectors.kcu_candidate_contract import (
    WATCH_CANDIDATE_TYPES,
    FORBIDDEN_CANDIDATE_TYPES,
    KCUSourceStatus,
    CONTRACT,
)
from src.detectors.base_detector import BaseDetector, DetectorConfig
from src.detectors.ltp_detector import LTPDetector
from src.detectors.rejection_detector import RejectionDetector
from src.detectors.reversal_detector import ReversalDetector
from src.detectors.bounce_detector import BounceDetector
from src.detectors.failed_ltp_watch_detector import FailedLTPWatchDetector
from src.detectors.chop_detector import ChopDetector
from src.detectors.detector_engine import DetectorEngine
from src.features.feature_record import FeatureRecord


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

TS_BASE = 1705329000  # 2024-01-15 09:30 ET


def _feat(
    ts: int = TS_BASE,
    idx: int = 0,
    o: float = 195.0,
    h: float = 197.0,
    l: float = 193.0,
    c: float = 196.0,
    v: float = 10000.0,
    atr: float | None = 2.0,
    body_pct: float | None = 50.0,
    upper_wick: float = 1.0,
    lower_wick: float = 1.0,
    is_hh: bool | None = None,
    is_ll: bool | None = None,
    is_inside: bool | None = None,
    is_outside: bool | None = None,
    consec_hh: int = 0,
    consec_ll: int = 0,
    consec_lh: int = 0,
    consec_hl: int = 0,
    rvol: float | None = None,
    session: str = "regular",
    t_since_open: float = 0.0,
    dist_open: float | None = 0.0,
    indicators: dict | None = None,
    symbol: str = "GENERIC",
    tf: str = "2",
    date: str = "2024-01-15",
) -> FeatureRecord:
    rng = h - l
    body = abs(c - o)
    return FeatureRecord(
        timestamp=ts, symbol=symbol, timeframe=tf, replay_date=date,
        candle_index=idx, open=o, high=h, low=l, close=c, volume=v,
        candle_body=body, upper_wick=upper_wick, lower_wick=lower_wick,
        body_pct=body_pct, candle_range=rng, atr=atr,
        gap_from_prev=None, distance_from_prev_close=None,
        is_higher_high=is_hh, is_lower_low=is_ll,
        is_inside_bar=is_inside, is_outside_bar=is_outside,
        consecutive_hh=consec_hh, consecutive_ll=consec_ll,
        consecutive_lh=consec_lh, consecutive_hl=consec_hl,
        relative_volume=rvol, session=session,
        time_since_open_minutes=t_since_open,
        distance_from_session_open=dist_open,
        indicators=indicators or {},
    )


def _prior(ts: int = TS_BASE - 120, **kw) -> FeatureRecord:
    return _feat(ts=ts, idx=0, **kw)


def _make_event(**overrides) -> CandidateEvent:
    base = dict(
        timestamp=TS_BASE, symbol="GENERIC", timeframe="2",
        replay_date="2024-01-15", candle_index=0,
        candidate_type="LTP_WATCH",
        source_status=KCUSourceStatus.HYPOTHESIS,
        reasons=["r1"], reason_codes=["COMPRESSED_RANGE"],
        supporting_features={"atr": 2.0},
        supporting_components=["patience_candle"],
        required_missing_components=["level_context", "trend_context"],
        invalidating_components=["range_expansion_below_compression"],
        no_trade_risk=["level_context_unverified"],
    )
    base.update(overrides)
    return CandidateEvent(**base)


# ------------------------------------------------------------------
# KCU Candidate Contract
# ------------------------------------------------------------------

class TestKCUCandidateContract:
    def test_watch_types_are_defined(self):
        assert "LTP_WATCH" in WATCH_CANDIDATE_TYPES
        assert "REJECTION_WATCH" in WATCH_CANDIDATE_TYPES
        assert "REVERSAL_WATCH" in WATCH_CANDIDATE_TYPES
        assert "BOUNCE_WATCH" in WATCH_CANDIDATE_TYPES
        assert "FAILED_LTP_WATCH" in WATCH_CANDIDATE_TYPES
        assert "CHOP" in WATCH_CANDIDATE_TYPES

    def test_forbidden_types_include_valid_ltp(self):
        assert "VALID_LTP" in FORBIDDEN_CANDIDATE_TYPES

    def test_forbidden_types_include_unqualified_ltp(self):
        assert "LTP" in FORBIDDEN_CANDIDATE_TYPES
        assert "REJECTION" in FORBIDDEN_CANDIDATE_TYPES
        assert "REVERSAL" in FORBIDDEN_CANDIDATE_TYPES
        assert "BOUNCE" in FORBIDDEN_CANDIDATE_TYPES

    def test_no_overlap_between_watch_and_forbidden(self):
        assert WATCH_CANDIDATE_TYPES.isdisjoint(FORBIDDEN_CANDIDATE_TYPES)

    def test_source_status_values_defined(self):
        assert KCUSourceStatus.HYPOTHESIS == "HYPOTHESIS"
        assert KCUSourceStatus.PARTIALLY_COVERED == "PARTIALLY_COVERED"
        assert KCUSourceStatus.CONFIRMED == "CONFIRMED"

    def test_watch_values_exclude_confirmed(self):
        assert KCUSourceStatus.CONFIRMED not in KCUSourceStatus.WATCH_VALUES

    def test_contract_covers_all_watch_types(self):
        for ct in WATCH_CANDIDATE_TYPES:
            assert ct in CONTRACT, f"{ct} missing from CONTRACT"

    def test_ltp_contract_has_patience_candle_as_detectable(self):
        assert "patience_candle" in CONTRACT["LTP_WATCH"]["detectable"]

    def test_ltp_contract_missing_level_and_trend(self):
        missing = CONTRACT["LTP_WATCH"]["missing"]
        assert "level_context" in missing
        assert "trend_context" in missing

    def test_ltp_is_hypothesis(self):
        assert CONTRACT["LTP_WATCH"]["source_status"] == KCUSourceStatus.HYPOTHESIS

    def test_reversal_is_partially_covered(self):
        assert CONTRACT["REVERSAL_WATCH"]["source_status"] == KCUSourceStatus.PARTIALLY_COVERED

    def test_bounce_is_partially_covered(self):
        assert CONTRACT["BOUNCE_WATCH"]["source_status"] == KCUSourceStatus.PARTIALLY_COVERED

    def test_all_contracts_have_no_trade_risk(self):
        for ct, spec in CONTRACT.items():
            assert spec["no_trade_risk"], f"{ct} has empty no_trade_risk"

    def test_all_contracts_have_invalidating_components(self):
        for ct, spec in CONTRACT.items():
            assert spec["invalidating"], f"{ct} has empty invalidating_components"


# ------------------------------------------------------------------
# CandidateEvent
# ------------------------------------------------------------------

class TestCandidateEvent:
    def test_valid_event_passes_validation(self):
        e = _make_event()
        assert e.validate() == []

    def test_forbidden_candidate_type_fails(self):
        e = _make_event(candidate_type="VALID_LTP")
        errors = e.validate()
        assert any("forbidden" in err.lower() for err in errors)

    def test_unqualified_ltp_type_fails(self):
        e = _make_event(candidate_type="LTP")
        errors = e.validate()
        assert any("forbidden" in err.lower() for err in errors)

    def test_confirmed_status_fails(self):
        e = _make_event(source_status=KCUSourceStatus.CONFIRMED)
        errors = e.validate()
        assert any("CONFIRMED" in err for err in errors)

    def test_invalid_source_status_fails(self):
        e = _make_event(source_status="UNKNOWN")
        errors = e.validate()
        assert any("source_status" in err for err in errors)

    def test_negative_candle_index_fails(self):
        e = _make_event(candle_index=-1)
        assert any("candle_index" in err for err in e.validate())

    def test_empty_no_trade_risk_fails(self):
        e = _make_event(no_trade_risk=[])
        errors = e.validate()
        assert any("no_trade_risk" in err for err in errors)

    def test_all_watch_types_pass(self):
        for ct in WATCH_CANDIDATE_TYPES:
            e = _make_event(candidate_type=ct)
            assert e.validate() == [], f"{ct} should be valid"

    def test_hypothesis_status_passes(self):
        e = _make_event(source_status=KCUSourceStatus.HYPOTHESIS)
        assert e.validate() == []

    def test_partially_covered_status_passes(self):
        e = _make_event(source_status=KCUSourceStatus.PARTIALLY_COVERED)
        assert e.validate() == []

    def test_to_dict_has_all_kcu_fields(self):
        e = _make_event()
        d = e.to_dict()
        for key in (
            "timestamp", "symbol", "candidate_type", "source_status",
            "reasons", "reason_codes", "supporting_features",
            "supporting_components", "required_missing_components",
            "invalidating_components", "no_trade_risk",
        ):
            assert key in d, f"Missing field: {key}"

    def test_to_jsonl_line_is_single_line(self):
        e = _make_event()
        line = e.to_jsonl_line()
        assert "\n" not in line
        parsed = json.loads(line)
        assert parsed["candidate_type"] == "LTP_WATCH"
        assert parsed["source_status"] == "HYPOTHESIS"

    def test_roundtrip_from_dict(self):
        e = _make_event(
            supporting_components=["patience_candle"],
            required_missing_components=["level_context"],
        )
        e2 = CandidateEvent.from_dict(e.to_dict())
        assert e2.candidate_type == e.candidate_type
        assert e2.source_status == e.source_status
        assert e2.supporting_components == e.supporting_components
        assert e2.required_missing_components == e.required_missing_components
        assert e2.no_trade_risk == e.no_trade_risk


# ------------------------------------------------------------------
# DetectorConfig
# ------------------------------------------------------------------

class TestDetectorConfig:
    def test_defaults_are_valid(self):
        cfg = DetectorConfig()
        assert cfg.ltp_compression_ratio == 0.5
        assert cfg.rev_min_streak == 2

    def test_invalid_compression_ratio_raises(self):
        with pytest.raises(ValueError, match="ltp_compression_ratio"):
            DetectorConfig(ltp_compression_ratio=0.0)

    def test_invalid_wick_range_pct_raises(self):
        with pytest.raises(ValueError, match="rej_wick_range_pct"):
            DetectorConfig(rej_wick_range_pct=1.0)

    def test_expansion_must_exceed_compression_raises(self):
        with pytest.raises(ValueError, match="failed_ltp_expansion_ratio"):
            DetectorConfig(failed_ltp_compression_ratio=0.8, failed_ltp_expansion_ratio=0.5)

    def test_min_streak_zero_raises(self):
        with pytest.raises(ValueError, match="rev_min_streak"):
            DetectorConfig(rev_min_streak=0)


# ------------------------------------------------------------------
# LTPDetector
# ------------------------------------------------------------------

class TestLTPDetector:
    def setup_method(self):
        self.det = LTPDetector()

    def test_emits_ltp_watch_not_ltp(self):
        f = _feat(h=195.4, l=194.6, atr=2.0, body_pct=30.0,
                  upper_wick=0.28, lower_wick=0.28)
        e = self.det.detect(f, ())
        assert e is not None
        assert e.candidate_type == "LTP_WATCH"
        assert e.candidate_type != "LTP"
        assert e.candidate_type != "VALID_LTP"

    def test_source_status_is_hypothesis(self):
        f = _feat(h=195.4, l=194.6, atr=2.0, body_pct=30.0,
                  upper_wick=0.28, lower_wick=0.28)
        e = self.det.detect(f, ())
        assert e is not None
        assert e.source_status == KCUSourceStatus.HYPOTHESIS

    def test_level_and_trend_context_in_missing(self):
        f = _feat(h=195.4, l=194.6, atr=2.0, body_pct=30.0,
                  upper_wick=0.28, lower_wick=0.28)
        e = self.det.detect(f, ())
        assert e is not None
        assert "level_context" in e.required_missing_components
        assert "trend_context" in e.required_missing_components

    def test_patience_candle_in_supporting_components(self):
        f = _feat(h=195.4, l=194.6, atr=2.0, body_pct=30.0,
                  upper_wick=0.28, lower_wick=0.28)
        e = self.det.detect(f, ())
        assert e is not None
        assert "patience_candle" in e.supporting_components

    def test_no_trade_risk_is_populated(self):
        f = _feat(h=195.4, l=194.6, atr=2.0, body_pct=30.0,
                  upper_wick=0.28, lower_wick=0.28)
        e = self.det.detect(f, ())
        assert e is not None
        assert len(e.no_trade_risk) > 0

    def test_invalidating_components_present(self):
        f = _feat(h=195.4, l=194.6, atr=2.0, body_pct=30.0,
                  upper_wick=0.28, lower_wick=0.28)
        e = self.det.detect(f, ())
        assert e is not None
        assert len(e.invalidating_components) > 0

    def test_reason_codes_populated(self):
        f = _feat(h=195.4, l=194.6, atr=2.0, body_pct=30.0,
                  upper_wick=0.28, lower_wick=0.28)
        e = self.det.detect(f, ())
        assert e is not None
        assert "COMPRESSED_RANGE" in e.reason_codes

    def test_no_atr_returns_none(self):
        f = _feat(atr=None)
        assert self.det.detect(f, ()) is None

    def test_range_above_threshold_returns_none(self):
        f = _feat(h=197.0, l=193.0, atr=2.0, body_pct=35.0)
        assert self.det.detect(f, ()) is None

    def test_large_body_pct_returns_none(self):
        f = _feat(h=195.3, l=194.8, atr=2.0, body_pct=80.0,
                  upper_wick=0.1, lower_wick=0.1)
        assert self.det.detect(f, ()) is None

    def test_doji_fires(self):
        f = _feat(h=195.4, l=194.6, o=195.0, c=195.0, atr=2.0, body_pct=None,
                  upper_wick=0.4, lower_wick=0.4)
        e = self.det.detect(f, ())
        assert e is not None
        assert e.candidate_type == "LTP_WATCH"

    def test_event_is_valid(self):
        f = _feat(h=195.4, l=194.6, atr=2.0, body_pct=30.0,
                  upper_wick=0.28, lower_wick=0.28)
        e = self.det.detect(f, ())
        assert e is not None
        assert e.validate() == []

    def test_custom_config_changes_threshold(self):
        cfg = DetectorConfig(ltp_compression_ratio=0.1)
        det = LTPDetector(cfg)
        f = _feat(h=195.4, l=194.6, atr=2.0, body_pct=30.0,
                  upper_wick=0.28, lower_wick=0.28)
        assert det.detect(f, ()) is None


# ------------------------------------------------------------------
# RejectionDetector
# ------------------------------------------------------------------

class TestRejectionDetector:
    def setup_method(self):
        self.det = RejectionDetector()

    def test_emits_rejection_watch(self):
        f = _feat(h=198.0, l=194.0, o=195.0, c=195.0,
                  upper_wick=3.0, lower_wick=0.0, body_pct=0.0)
        e = self.det.detect(f, ())
        assert e is not None
        assert e.candidate_type == "REJECTION_WATCH"
        assert e.candidate_type != "REJECTION"

    def test_source_status_is_hypothesis(self):
        f = _feat(h=198.0, l=194.0, o=195.0, c=195.0,
                  upper_wick=3.0, lower_wick=0.0, body_pct=0.0)
        e = self.det.detect(f, ())
        assert e is not None
        assert e.source_status == KCUSourceStatus.HYPOTHESIS

    def test_level_and_directional_context_missing(self):
        f = _feat(h=198.0, l=194.0, o=195.0, c=195.0,
                  upper_wick=3.0, lower_wick=0.0, body_pct=0.0)
        e = self.det.detect(f, ())
        assert e is not None
        assert "level_context" in e.required_missing_components
        assert "directional_context" in e.required_missing_components

    def test_rejection_wick_in_supporting(self):
        f = _feat(h=198.0, l=194.0, o=195.0, c=195.0,
                  upper_wick=3.0, lower_wick=0.0, body_pct=0.0)
        e = self.det.detect(f, ())
        assert e is not None
        assert "rejection_wick" in e.supporting_components

    def test_no_trade_risk_populated(self):
        f = _feat(h=198.0, l=194.0, o=195.0, c=195.0,
                  upper_wick=3.0, lower_wick=0.0, body_pct=0.0)
        e = self.det.detect(f, ())
        assert e is not None
        assert len(e.no_trade_risk) > 0

    def test_upper_rejection(self):
        f = _feat(h=198.0, l=194.0, o=195.0, c=195.0,
                  upper_wick=3.0, lower_wick=0.0, body_pct=0.0)
        e = self.det.detect(f, ())
        assert e is not None
        assert e.supporting_features["rejection_direction"] == "upper"

    def test_lower_rejection(self):
        f = _feat(h=197.0, l=193.0, o=196.0, c=196.0,
                  upper_wick=0.0, lower_wick=3.0, body_pct=0.0)
        e = self.det.detect(f, ())
        assert e is not None
        assert e.supporting_features["rejection_direction"] == "lower"

    def test_both_rejection(self):
        f = _feat(h=198.0, l=192.0, o=195.0, c=195.0,
                  upper_wick=3.0, lower_wick=3.0, body_pct=None)
        e = self.det.detect(f, ())
        assert e is not None
        assert e.supporting_features["rejection_direction"] == "both"

    def test_no_range_returns_none(self):
        f = _feat(h=195.0, l=195.0, o=195.0, c=195.0,
                  upper_wick=0.0, lower_wick=0.0, body_pct=None)
        assert self.det.detect(f, ()) is None

    def test_wick_too_small_returns_none(self):
        f = _feat(h=197.5, l=194.5, o=195.0, c=197.0,
                  upper_wick=0.5, lower_wick=0.5, body_pct=66.0)
        assert self.det.detect(f, ()) is None

    def test_event_is_valid(self):
        f = _feat(h=198.0, l=194.0, o=195.0, c=195.0,
                  upper_wick=3.0, lower_wick=0.0, body_pct=0.0)
        e = self.det.detect(f, ())
        assert e is not None
        assert e.validate() == []


# ------------------------------------------------------------------
# ReversalDetector
# ------------------------------------------------------------------

class TestReversalDetector:
    def setup_method(self):
        self.det = ReversalDetector()

    def test_emits_reversal_watch(self):
        w = (_prior(),)
        f = _feat(consec_hh=2, is_hh=False, is_ll=True, o=197.0, c=195.0)
        e = self.det.detect(f, w)
        assert e is not None
        assert e.candidate_type == "REVERSAL_WATCH"
        assert e.candidate_type != "REVERSAL"

    def test_source_status_is_partially_covered(self):
        w = (_prior(),)
        f = _feat(consec_hh=2, is_hh=False, is_ll=True, o=197.0, c=195.0)
        e = self.det.detect(f, w)
        assert e is not None
        assert e.source_status == KCUSourceStatus.PARTIALLY_COVERED

    def test_two_components_detectable(self):
        w = (_prior(),)
        f = _feat(consec_hh=2, is_hh=False, is_ll=True, o=197.0, c=195.0)
        e = self.det.detect(f, w)
        assert e is not None
        assert "trend_exhaustion" in e.supporting_components
        assert "change_of_character" in e.supporting_components

    def test_level_context_missing(self):
        w = (_prior(),)
        f = _feat(consec_hh=2, is_hh=False, is_ll=True, o=197.0, c=195.0)
        e = self.det.detect(f, w)
        assert e is not None
        assert "level_context" in e.required_missing_components

    def test_no_trade_risk_populated(self):
        w = (_prior(),)
        f = _feat(consec_hh=2, is_hh=False, is_ll=True, o=197.0, c=195.0)
        e = self.det.detect(f, w)
        assert e is not None
        assert len(e.no_trade_risk) > 0

    def test_bearish_reversal_fires(self):
        w = (_prior(),)
        f = _feat(consec_hh=2, is_hh=False, is_ll=True, o=197.0, c=195.0)
        e = self.det.detect(f, w)
        assert e is not None
        assert e.supporting_features["direction"] == "bearish"

    def test_bullish_reversal_fires(self):
        w = (_prior(),)
        f = _feat(consec_ll=2, is_ll=False, is_hh=True, o=193.0, c=195.0)
        e = self.det.detect(f, w)
        assert e is not None
        assert e.supporting_features["direction"] == "bullish"

    def test_empty_window_returns_none(self):
        f = _feat(consec_hh=3, is_hh=False, c=194.0, o=196.0)
        assert self.det.detect(f, ()) is None

    def test_no_streak_returns_none(self):
        w = (_prior(),)
        f = _feat(consec_hh=1, is_hh=False, is_ll=True, o=196.0, c=194.0)
        assert self.det.detect(f, w) is None

    def test_bearish_body_required(self):
        w = (_prior(),)
        f = _feat(consec_hh=2, is_hh=False, is_ll=True, o=195.0, c=197.0)
        assert self.det.detect(f, w) is None

    def test_event_is_valid(self):
        w = (_prior(),)
        f = _feat(consec_hh=2, is_hh=False, is_ll=True, o=197.0, c=195.0)
        e = self.det.detect(f, w)
        assert e is not None
        assert e.validate() == []


# ------------------------------------------------------------------
# BounceDetector
# ------------------------------------------------------------------

class TestBounceDetector:
    def setup_method(self):
        self.det = BounceDetector()

    def test_emits_bounce_watch(self):
        w = (_prior(),)
        f = _feat(is_ll=False, is_hh=True,
                  lower_wick=2.0, upper_wick=0.5, o=195.0, c=195.2)
        e = self.det.detect(f, w)
        assert e is not None
        assert e.candidate_type == "BOUNCE_WATCH"
        assert e.candidate_type != "BOUNCE"

    def test_source_status_is_partially_covered(self):
        w = (_prior(),)
        f = _feat(is_ll=False, is_hh=True,
                  lower_wick=2.0, upper_wick=0.5, o=195.0, c=195.2)
        e = self.det.detect(f, w)
        assert e is not None
        assert e.source_status == KCUSourceStatus.PARTIALLY_COVERED

    def test_two_components_detectable(self):
        w = (_prior(),)
        f = _feat(is_ll=False, is_hh=True,
                  lower_wick=2.0, upper_wick=0.5, o=195.0, c=195.2)
        e = self.det.detect(f, w)
        assert e is not None
        assert "support_reaction" in e.supporting_components
        assert "directional_wick" in e.supporting_components

    def test_level_context_missing(self):
        w = (_prior(),)
        f = _feat(is_ll=False, is_hh=True,
                  lower_wick=2.0, upper_wick=0.5, o=195.0, c=195.2)
        e = self.det.detect(f, w)
        assert e is not None
        assert "level_context" in e.required_missing_components

    def test_no_trade_risk_populated(self):
        w = (_prior(),)
        f = _feat(is_ll=False, is_hh=True,
                  lower_wick=2.0, upper_wick=0.5, o=195.0, c=195.2)
        e = self.det.detect(f, w)
        assert e is not None
        assert len(e.no_trade_risk) > 0

    def test_bullish_bounce(self):
        w = (_prior(),)
        f = _feat(is_ll=False, is_hh=True,
                  lower_wick=2.0, upper_wick=0.5, o=195.0, c=195.2)
        e = self.det.detect(f, w)
        assert e is not None
        assert e.supporting_features["direction"] == "bullish"

    def test_bearish_bounce(self):
        w = (_prior(),)
        f = _feat(is_hh=False, is_ll=True,
                  upper_wick=2.0, lower_wick=0.5, o=197.0, c=196.8)
        e = self.det.detect(f, w)
        assert e is not None
        assert e.supporting_features["direction"] == "bearish"

    def test_empty_window_returns_none(self):
        f = _feat(is_ll=False, lower_wick=2.0, upper_wick=0.5)
        assert self.det.detect(f, ()) is None

    def test_new_low_no_bounce(self):
        w = (_prior(),)
        f = _feat(is_ll=True, is_hh=False,
                  lower_wick=2.0, upper_wick=0.5, o=195.0, c=194.0)
        assert self.det.detect(f, w) is None

    def test_event_is_valid(self):
        w = (_prior(),)
        f = _feat(is_ll=False, is_hh=True,
                  lower_wick=2.0, upper_wick=0.5, o=195.0, c=195.2)
        e = self.det.detect(f, w)
        assert e is not None
        assert e.validate() == []


# ------------------------------------------------------------------
# FailedLTPWatchDetector
# ------------------------------------------------------------------

class TestFailedLTPWatchDetector:
    def setup_method(self):
        self.det = FailedLTPWatchDetector()

    def test_emits_failed_ltp_watch(self):
        prior = _prior(h=195.3, l=194.7, atr=2.0)
        f = _feat(h=196.0, l=194.0, atr=2.0, body_pct=20.0,
                  upper_wick=0.9, lower_wick=0.7)
        e = self.det.detect(f, (prior,))
        assert e is not None
        assert e.candidate_type == "FAILED_LTP_WATCH"

    def test_source_status_is_partially_covered(self):
        prior = _prior(h=195.3, l=194.7, atr=2.0)
        f = _feat(h=196.0, l=194.0, atr=2.0, body_pct=20.0,
                  upper_wick=0.9, lower_wick=0.7)
        e = self.det.detect(f, (prior,))
        assert e is not None
        assert e.source_status == KCUSourceStatus.PARTIALLY_COVERED

    def test_both_components_in_supporting(self):
        prior = _prior(h=195.3, l=194.7, atr=2.0)
        f = _feat(h=196.0, l=194.0, atr=2.0, body_pct=20.0,
                  upper_wick=0.9, lower_wick=0.7)
        e = self.det.detect(f, (prior,))
        assert e is not None
        assert "prior_compression" in e.supporting_components
        assert "expansion_failure" in e.supporting_components

    def test_no_trade_risk_populated(self):
        prior = _prior(h=195.3, l=194.7, atr=2.0)
        f = _feat(h=196.0, l=194.0, atr=2.0, body_pct=20.0,
                  upper_wick=0.9, lower_wick=0.7)
        e = self.det.detect(f, (prior,))
        assert e is not None
        assert len(e.no_trade_risk) > 0

    def test_empty_window_returns_none(self):
        assert self.det.detect(_feat(atr=2.0), ()) is None

    def test_prior_not_compressed_returns_none(self):
        prior = _prior(atr=2.0)  # default h=197, l=193 → range=4 > 2*0.5=1
        f = _feat(atr=2.0)
        assert self.det.detect(f, (prior,)) is None

    def test_event_is_valid(self):
        prior = _prior(h=195.3, l=194.7, atr=2.0)
        f = _feat(h=196.0, l=194.0, atr=2.0, body_pct=20.0,
                  upper_wick=0.9, lower_wick=0.7, idx=1)
        e = self.det.detect(f, (prior,))
        assert e is not None
        assert e.validate() == []


# ------------------------------------------------------------------
# ChopDetector
# ------------------------------------------------------------------

class TestChopDetector:
    def setup_method(self):
        self.det = ChopDetector()

    def test_emits_chop(self):
        w = (_prior(),)
        f = _feat(is_inside=True, is_hh=False, is_ll=False, body_pct=30.0)
        e = self.det.detect(f, w)
        assert e is not None
        assert e.candidate_type == "CHOP"

    def test_source_status_is_partially_covered(self):
        w = (_prior(),)
        f = _feat(is_inside=True, is_hh=False, is_ll=False, body_pct=30.0)
        e = self.det.detect(f, w)
        assert e is not None
        assert e.source_status == KCUSourceStatus.PARTIALLY_COVERED

    def test_contained_range_in_supporting(self):
        w = (_prior(),)
        f = _feat(is_inside=True, is_hh=False, is_ll=False, body_pct=30.0)
        e = self.det.detect(f, w)
        assert e is not None
        assert "contained_range" in e.supporting_components

    def test_no_trade_risk_populated(self):
        w = (_prior(),)
        f = _feat(is_inside=True, is_hh=False, is_ll=False, body_pct=30.0)
        e = self.det.detect(f, w)
        assert e is not None
        assert len(e.no_trade_risk) > 0

    def test_inside_bar_fires(self):
        w = (_prior(),)
        f = _feat(is_inside=True, is_hh=False, is_ll=False, body_pct=30.0)
        e = self.det.detect(f, w)
        assert e is not None
        assert "inside_bar" in e.supporting_features["chop_trigger"]

    def test_structural_chop_fires(self):
        w = (_prior(),)
        f = _feat(is_inside=False, is_hh=False, is_ll=False, body_pct=15.0)
        e = self.det.detect(f, w)
        assert e is not None

    def test_new_high_no_chop(self):
        w = (_prior(),)
        f = _feat(is_inside=False, is_hh=True, is_ll=False, body_pct=15.0)
        assert self.det.detect(f, w) is None

    def test_empty_window_returns_none(self):
        f = _feat(is_inside=True)
        assert self.det.detect(f, ()) is None

    def test_event_is_valid(self):
        w = (_prior(),)
        f = _feat(is_inside=True, is_hh=False, is_ll=False, body_pct=30.0)
        e = self.det.detect(f, w)
        assert e is not None
        assert e.validate() == []


# ------------------------------------------------------------------
# DetectorEngine
# ------------------------------------------------------------------

class TestDetectorEngine:
    def test_requires_at_least_one_detector(self):
        with pytest.raises(ValueError, match="at least one"):
            DetectorEngine(detectors=[])

    def test_default_factory_creates_six_detectors(self):
        engine = DetectorEngine.default()
        assert len(engine.detector_types) == 6

    def test_default_includes_all_watch_types(self):
        engine = DetectorEngine.default()
        types = set(engine.detector_types)
        assert "LTP_WATCH" in types
        assert "REJECTION_WATCH" in types
        assert "REVERSAL_WATCH" in types
        assert "BOUNCE_WATCH" in types
        assert "FAILED_LTP_WATCH" in types
        assert "CHOP" in types

    def test_no_unqualified_types_in_default(self):
        engine = DetectorEngine.default()
        types = set(engine.detector_types)
        assert "LTP" not in types
        assert "REJECTION" not in types
        assert "REVERSAL" not in types
        assert "BOUNCE" not in types

    def test_all_events_are_candidate_events(self):
        engine = DetectorEngine.default()
        records = [_feat(ts=TS_BASE + i * 120, idx=i) for i in range(5)]
        events = engine.run(records)
        for e in events:
            assert isinstance(e, CandidateEvent)

    def test_all_events_pass_validation(self):
        engine = DetectorEngine.default()
        records = [
            _feat(ts=TS_BASE + i * 120, idx=i,
                  is_hh=True if i % 2 == 0 else False,
                  is_ll=False if i % 2 == 0 else True,
                  consec_hh=i, atr=2.0)
            for i in range(5)
        ]
        events = engine.run(records)
        for e in events:
            assert e.validate() == [], (
                f"Event {e.candidate_type} at candle {e.candle_index} invalid: {e.validate()}"
            )

    def test_window_does_not_contain_current_candle(self):
        seen_windows: list[tuple[int, list[int]]] = []

        class WindowCapturing(BaseDetector):
            @property
            def candidate_type(self) -> str:
                return "LTP_WATCH"

            def detect(self, features, window):
                seen_windows.append((features.candle_index, [r.candle_index for r in window]))
                return None

        engine = DetectorEngine(detectors=[WindowCapturing()])
        records = [_feat(ts=TS_BASE + i * 120, idx=i) for i in range(4)]
        engine.run(records)
        for current_idx, window_indices in seen_windows:
            assert current_idx not in window_indices

    def test_window_only_contains_past_candles(self):
        class Inspector(BaseDetector):
            @property
            def candidate_type(self) -> str:
                return "LTP_WATCH"

            def detect(self, features, window):
                for r in window:
                    assert r.candle_index < features.candle_index
                return None

        engine = DetectorEngine(detectors=[Inspector()])
        records = [_feat(ts=TS_BASE + i * 120, idx=i) for i in range(6)]
        engine.run(records)

    def test_plugin_register_adds_detector(self):
        class CustomDetector(BaseDetector):
            @property
            def candidate_type(self) -> str:
                return "LTP_WATCH"

            def detect(self, features, window):
                return None

        engine = DetectorEngine(detectors=[LTPDetector()])
        initial = len(engine.detector_types)
        engine.register(CustomDetector())
        assert len(engine.detector_types) == initial + 1

    def test_custom_plugin_fires(self):
        class AlwaysChop(BaseDetector):
            @property
            def candidate_type(self) -> str:
                return "CHOP"

            def detect(self, features, window):
                return self._make_event(
                    features,
                    source_status=KCUSourceStatus.PARTIALLY_COVERED,
                    reasons=["always"],
                    reason_codes=["STRUCTURAL_CHOP"],
                    supporting_features={},
                    supporting_components=["contained_range"],
                    required_missing_components=[],
                    invalidating_components=["directional_range_expansion"],
                    no_trade_risk=["no_directional_bias"],
                )

        engine = DetectorEngine(detectors=[AlwaysChop()])
        records = [_feat(ts=TS_BASE + i * 120, idx=i) for i in range(3)]
        events = engine.run(records)
        assert len(events) == 3

    def test_reset_clears_window(self):
        engine = DetectorEngine.default()
        engine.run([_feat(ts=TS_BASE + i * 120, idx=i) for i in range(3)])
        engine.reset()
        events = engine.process(_feat(ts=TS_BASE + 1000, idx=100))
        assert isinstance(events, list)

    def test_events_chronological(self):
        engine = DetectorEngine.default()
        records = [_feat(ts=TS_BASE + i * 120, idx=i, atr=2.0) for i in range(10)]
        events = engine.run(records)
        timestamps = [e.timestamp for e in events]
        assert timestamps == sorted(timestamps)

    def test_determinism(self):
        records = [
            _feat(ts=TS_BASE + i * 120, idx=i,
                  h=197.0 + i * 0.3, l=193.0, atr=2.0,
                  is_hh=True, consec_hh=i)
            for i in range(5)
        ]
        engine1 = DetectorEngine.default()
        engine2 = DetectorEngine.default()
        assert (
            [e.to_dict() for e in engine1.run(records)]
            == [e.to_dict() for e in engine2.run(records)]
        )


# ------------------------------------------------------------------
# Integration: LTP_WATCH → FAILED_LTP_WATCH sequence
# ------------------------------------------------------------------

class TestLTPToFailedSequence:
    def test_compression_then_indecisive_expansion(self):
        engine = DetectorEngine.default()
        c0 = _feat(ts=TS_BASE, idx=0, h=197.0, l=193.0, atr=None)
        c1 = _feat(ts=TS_BASE + 120, idx=1, h=195.4, l=194.6, atr=2.0, body_pct=30.0,
                   upper_wick=0.28, lower_wick=0.28)
        c2 = _feat(ts=TS_BASE + 240, idx=2, h=197.0, l=194.0, atr=2.0, body_pct=20.0,
                   upper_wick=0.9, lower_wick=0.7)
        all_events = engine.run([c0, c1, c2])
        types = [e.candidate_type for e in all_events]
        assert "LTP_WATCH" in types
        assert "FAILED_LTP_WATCH" in types


# ------------------------------------------------------------------
# KCU Audit Tests
# ------------------------------------------------------------------

class TestKCUAudit:
    """Prove that no detector emits invalid setup labels or implies trade validity."""

    def _all_events(self) -> list[CandidateEvent]:
        """Run the default engine on a wide variety of candles and collect all events."""
        engine = DetectorEngine.default()
        records = []
        base_ts = TS_BASE
        for i in range(30):
            records.append(_feat(
                ts=base_ts + i * 120, idx=i,
                h=197.0 + (i % 5) * 0.5,
                l=193.0 - (i % 3) * 0.3,
                o=195.0 + (i % 4) * 0.2,
                c=195.5 + (i % 6) * 0.15,
                atr=2.0,
                body_pct=float((i * 13) % 90),
                upper_wick=0.5 + (i % 5) * 0.3,
                lower_wick=0.3 + (i % 4) * 0.25,
                is_hh=bool(i % 2),
                is_ll=bool((i + 1) % 3),
                is_inside=bool(i % 5 == 0),
                consec_hh=i % 4,
                consec_ll=i % 3,
            ))
        return engine.run(records)

    def test_no_event_has_valid_ltp_type(self):
        for e in self._all_events():
            assert e.candidate_type != "VALID_LTP", (
                f"Detector emitted forbidden type VALID_LTP at candle {e.candle_index}"
            )

    def test_no_event_has_unqualified_ltp_type(self):
        for e in self._all_events():
            assert e.candidate_type not in FORBIDDEN_CANDIDATE_TYPES, (
                f"Detector emitted forbidden type {e.candidate_type!r}"
            )

    def test_all_event_types_are_watch_variants(self):
        for e in self._all_events():
            assert e.candidate_type in WATCH_CANDIDATE_TYPES, (
                f"Unexpected candidate_type: {e.candidate_type!r}"
            )

    def test_no_event_is_confirmed(self):
        for e in self._all_events():
            assert e.source_status != KCUSourceStatus.CONFIRMED, (
                f"Detector emitted CONFIRMED status at candle {e.candle_index}"
            )

    def test_all_events_have_no_trade_risk(self):
        for e in self._all_events():
            assert len(e.no_trade_risk) > 0, (
                f"{e.candidate_type} at candle {e.candle_index} has empty no_trade_risk"
            )

    def test_all_events_pass_validation(self):
        for e in self._all_events():
            errors = e.validate()
            assert errors == [], (
                f"{e.candidate_type} at candle {e.candle_index}: {errors}"
            )

    def test_ltp_watch_always_missing_level_context(self):
        engine = DetectorEngine.default()
        records = [
            _feat(ts=TS_BASE + i * 120, idx=i, h=195.3, l=194.7, atr=2.0, body_pct=25.0,
                  upper_wick=0.25, lower_wick=0.25)
            for i in range(5)
        ]
        events = engine.run(records)
        ltp_events = [e for e in events if e.candidate_type == "LTP_WATCH"]
        assert len(ltp_events) > 0, "No LTP_WATCH events produced from compressed candles"
        for e in ltp_events:
            assert "level_context" in e.required_missing_components, (
                f"LTP_WATCH at {e.candle_index} missing 'level_context' in required_missing_components"
            )
            assert "trend_context" in e.required_missing_components, (
                f"LTP_WATCH at {e.candle_index} missing 'trend_context' in required_missing_components"
            )

    def test_no_detector_implies_entry(self):
        """No event's required_confirmation or no_trade_risk should contain entry/stop/target."""
        forbidden_in_confirmations = {"entry", "stop", "target", "stop_loss", "take_profit"}
        for e in self._all_events():
            for phrase in e.no_trade_risk:
                for term in forbidden_in_confirmations:
                    assert term not in phrase.lower(), (
                        f"Trade-management term {term!r} found in no_trade_risk of "
                        f"{e.candidate_type}: {phrase!r}"
                    )

    def test_reason_codes_are_stable_strings(self):
        """reason_codes must be uppercase underscored identifiers."""
        import re
        pattern = re.compile(r'^[A-Z][A-Z0-9_]+$')
        for e in self._all_events():
            for code in e.reason_codes:
                assert pattern.match(code), (
                    f"reason_code {code!r} is not a stable uppercase identifier"
                )

    def test_supporting_components_match_contract(self):
        """Each supporting_component must be listed in the contract's detectable set."""
        for e in self._all_events():
            if e.candidate_type not in CONTRACT:
                continue
            detectable = set(CONTRACT[e.candidate_type]["detectable"])
            for comp in e.supporting_components:
                assert comp in detectable, (
                    f"{e.candidate_type} reported supporting_component {comp!r} "
                    f"which is not in contract detectable: {detectable}"
                )


# ------------------------------------------------------------------
# No trading logic in source code
# ------------------------------------------------------------------

FORBIDDEN_TERMS = [
    "stop_loss", "take_profit", "position_size", "risk_reward",
    "win_rate", "win rate", "probability", "edge_score",
    "setup_grade", "trade_quality", "buy signal", "sell signal",
    "valid_ltp", "ltp_confirmed",
]

DETECTOR_MODULES = [
    "src.detectors.ltp_detector",
    "src.detectors.rejection_detector",
    "src.detectors.reversal_detector",
    "src.detectors.bounce_detector",
    "src.detectors.chop_detector",
    "src.detectors.failed_ltp_watch_detector",
    "src.detectors.detector_engine",
    "src.detectors.base_detector",
    "src.detectors.candidate_event",
]


class TestNoBizLogicInSource:
    @pytest.mark.parametrize("module_path", DETECTOR_MODULES)
    def test_no_trading_terms(self, module_path):
        import importlib
        import inspect
        mod = importlib.import_module(module_path)
        src = inspect.getsource(mod).lower()
        for term in FORBIDDEN_TERMS:
            assert term not in src, (
                f"Forbidden term {term!r} found in {module_path}"
            )


class TestNoHardcodedTickers:
    TICKERS = ("TSLA", "AAPL", "SPY", "QQQ")

    @pytest.mark.parametrize("module_path", DETECTOR_MODULES)
    def test_no_hardcoded_tickers(self, module_path):
        import importlib
        import inspect
        mod = importlib.import_module(module_path)
        src = inspect.getsource(mod)
        for ticker in self.TICKERS:
            assert ticker not in src, (
                f"Ticker {ticker!r} hardcoded in {module_path}"
            )


class TestNoFutureCandles:
    def test_timestamps_in_window_always_before_current(self):
        observations: list[tuple[int, int]] = []

        class TimestampInspector(BaseDetector):
            @property
            def candidate_type(self) -> str:
                return "LTP_WATCH"

            def detect(self, features, window):
                for r in window:
                    observations.append((features.timestamp, r.timestamp))
                return None

        engine = DetectorEngine(detectors=[TimestampInspector()])
        records = [_feat(ts=TS_BASE + i * 120, idx=i) for i in range(6)]
        engine.run(records)
        for current_ts, window_ts in observations:
            assert window_ts < current_ts

    def test_no_replay_engine_import_in_detector_source(self):
        pkg_path = Path(__file__).parents[2] / "src" / "detectors"
        for f in pkg_path.glob("*.py"):
            tree = ast.parse(f.read_text())
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    module = getattr(node, "module", "") or ""
                    names = [a.name for a in getattr(node, "names", [])]
                    for ref in [module] + names:
                        assert "replay_engine" not in ref.lower(), (
                            f"{f.name} imports replay_engine: {ref}"
                        )
