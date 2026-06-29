"""Unit tests for the watch-only scenario layer."""
from __future__ import annotations

import json

import pytest

from src.detectors import (
    ScenarioConfidence,
    ScenarioType,
    ScenarioWatchEngine,
    load_scenario_events,
)
from src.detectors.scenario_event import ScenarioEvent
from src.features.feature_record import FeatureRecord
from src.features.level_context import LevelRecord, NamedLevel


def _feature(
    *,
    ts: int = 1782141000,
    idx: int = 0,
    close: float = 300.0,
    atr: float | None = 4.0,
    upper_wick: float = 1.0,
    lower_wick: float = 1.0,
    body: float = 0.6,
    is_lower_low: bool | None = False,
    is_higher_high: bool | None = False,
    consec_hh: int = 0,
    consec_hl: int = 0,
    consec_ll: int = 0,
    consec_lh: int = 0,
    session: str = "regular",
    time_since_open_minutes: float = 0.0,
    indicators: dict | None = None,
) -> FeatureRecord:
    return FeatureRecord(
        timestamp=ts,
        symbol="TSLA",
        timeframe="5",
        replay_date="2026-06-22",
        candle_index=idx,
        open=close - body,
        high=close + upper_wick,
        low=close - lower_wick,
        close=close,
        volume=10000.0,
        candle_body=body,
        upper_wick=upper_wick,
        lower_wick=lower_wick,
        body_pct=25.0,
        candle_range=upper_wick + lower_wick + body,
        atr=atr,
        gap_from_prev=None,
        distance_from_prev_close=None,
        is_higher_high=is_higher_high,
        is_lower_low=is_lower_low,
        is_inside_bar=None,
        is_outside_bar=None,
        consecutive_hh=consec_hh,
        consecutive_ll=consec_ll,
        consecutive_lh=consec_lh,
        consecutive_hl=consec_hl,
        relative_volume=None,
        session=session,
        time_since_open_minutes=time_since_open_minutes,
        distance_from_session_open=0.0,
        indicators=indicators or {},
    )


def _level_record(
    *,
    ts: int = 1782141000,
    idx: int = 0,
    close_level: float = 300.0,
    pdh: float | None = None,
    orh: float | None = None,
    vwap: float | None = None,
    touch: bool | None = None,
    reject: bool | None = None,
) -> LevelRecord:
    return LevelRecord(
        timestamp=ts,
        symbol="TSLA",
        timeframe="5",
        replay_date="2026-06-22",
        candle_index=idx,
        pmh=NamedLevel.unknown("PMH"),
        pml=NamedLevel.unknown("PML"),
        pdh=NamedLevel.derived("PDH", pdh) if pdh is not None else NamedLevel.unknown("PDH"),
        pdl=NamedLevel.unknown("PDL"),
        pdc=NamedLevel.unknown("PDC"),
        orh=NamedLevel.derived("ORH", orh) if orh is not None else NamedLevel.unknown("ORH"),
        orl=NamedLevel.unknown("ORL"),
        vwap=NamedLevel.derived("VWAP", vwap) if vwap is not None else NamedLevel.unknown("VWAP"),
        opening_price=NamedLevel.derived("OPEN", close_level),
        hourly_levels=[],
        level_touch=touch,
        level_reject=reject,
    )


class TestScenarioEvent:
    def test_round_trip(self):
        event = ScenarioEvent(
            timestamp=1782141000,
            symbol="TSLA",
            timeframe="5",
            replay_date="2026-06-22",
            candle_index=99,
            scenario_type=ScenarioType.BOUNCE_WATCH,
            approaching_levels=["PDH", "200 SMA 1h"],
            confluence_count=2,
            distance_to_zone=0.12,
            required_confirmation=["support_holds_at_zone"],
            invalidation_hint="lose support",
            detector_labels=["BOUNCE_WATCH"],
        )
        restored = ScenarioEvent.from_dict(event.to_dict())
        assert restored.to_dict() == event.to_dict()
        assert restored.validate() == []

    def test_requires_hypothesis_status(self):
        event = ScenarioEvent(
            timestamp=1782141000,
            symbol="TSLA",
            timeframe="5",
            replay_date="2026-06-22",
            candle_index=1,
            scenario_type=ScenarioType.REJECTION_WATCH,
            approaching_levels=["ORH", "PDH"],
            confluence_count=2,
            distance_to_zone=0.1,
            required_confirmation=["hold_zone"],
            invalidation_hint="reclaim zone",
            source_status="CONFIRMED",
        )
        assert any("source_status" in err for err in event.validate())


class TestScenarioWatchEngine:
    def test_premarket_scenarios_are_blocked_by_default(self):
        engine = ScenarioWatchEngine()
        feature = _feature(
            ts=1782129600,
            idx=10,
            close=300.0,
            lower_wick=2.2,
            body=0.5,
            session="premarket",
            time_since_open_minutes=-30.0,
            indicators={"KCU.200 SMA 1h": 300.15},
        )
        level = _level_record(
            ts=1782129600,
            idx=10,
            close_level=300.0,
            pdh=299.95,
            touch=True,
        )

        events = engine.step(feature, level, ["BOUNCE_WATCH"])

        assert events == []

    def test_premarket_scenarios_can_be_enabled_explicitly(self):
        from src.detectors.scenario_watch import ScenarioWatchConfig

        engine = ScenarioWatchEngine(
            ScenarioWatchConfig(emit_premarket_scenarios=True)
        )
        feature = _feature(
            ts=1782129600,
            idx=10,
            close=300.0,
            lower_wick=2.2,
            body=0.5,
            session="premarket",
            time_since_open_minutes=-30.0,
            indicators={"KCU.200 SMA 1h": 300.15},
        )
        level = _level_record(
            ts=1782129600,
            idx=10,
            close_level=300.0,
            pdh=299.95,
            touch=True,
        )

        events = engine.step(feature, level, ["BOUNCE_WATCH"])

        assert len(events) == 1
        assert events[0].scenario_type == ScenarioType.BOUNCE_WATCH

    def test_bounce_area_can_be_logged_from_pdh_and_200ma_confluence(self):
        engine = ScenarioWatchEngine()
        feature = _feature(
            ts=1782140100,
            idx=145,
            close=300.0,
            lower_wick=2.2,
            body=0.5,
            indicators={"KCU.200 SMA 1h": 300.15},
        )
        level = _level_record(
            ts=1782140100,
            idx=145,
            close_level=300.0,
            pdh=299.95,
            touch=True,
        )

        events = engine.step(feature, level, ["BOUNCE_WATCH"])

        assert len(events) == 1
        event = events[0]
        assert event.scenario_type == ScenarioType.BOUNCE_WATCH
        assert event.approaching_levels == ["PDH", "200 SMA 1h"]
        assert event.confluence_count == 2
        assert event.confidence == ScenarioConfidence.WATCH

    def test_rejection_area_can_be_logged_from_orh_pdh_and_200ma_confluence(self):
        engine = ScenarioWatchEngine()
        feature = _feature(
            ts=1782136200,
            idx=163,
            close=322.0,
            upper_wick=2.4,
            body=0.4,
            indicators={"KCU.200 SMA 1h": 322.2},
        )
        level = _level_record(
            ts=1782136200,
            idx=163,
            close_level=322.0,
            pdh=322.1,
            orh=321.95,
            reject=True,
        )

        events = engine.step(feature, level, ["REJECTION_WATCH"])

        assert len(events) == 1
        event = events[0]
        assert event.scenario_type == ScenarioType.REJECTION_WATCH
        assert event.approaching_levels == ["ORH", "PDH", "200 SMA 1h"]
        assert event.confluence_count == 3

    def test_failed_ltp_label_can_still_surface_rejection_watch(self):
        engine = ScenarioWatchEngine()
        feature = _feature(
            close=322.0,
            upper_wick=2.0,
            body=0.4,
            indicators={"KCU.200 SMA 1h": 322.2},
        )
        level = _level_record(pdh=322.1, orh=321.95, reject=True)

        events = engine.step(feature, level, ["FAILED_LTP_WATCH"])

        assert [event.scenario_type for event in events] == [ScenarioType.REJECTION_WATCH]

    def test_regular_session_bounce_can_emit_without_same_candle_detector_label(self):
        engine = ScenarioWatchEngine()
        feature = _feature(
            ts=1782140100,
            idx=145,
            close=300.0,
            upper_wick=0.6,
            lower_wick=1.3,
            body=1.0,
            is_lower_low=False,
            indicators={"KCU.200 SMA 1h": 300.15},
        )
        level = _level_record(
            ts=1782140100,
            idx=145,
            close_level=300.0,
            pdh=299.95,
            vwap=300.1,
            touch=False,
        )
        level.level_hold = True

        events = engine.step(feature, level, [])

        assert len(events) == 1
        assert events[0].scenario_type == ScenarioType.BOUNCE_WATCH
        assert events[0].approaching_levels == ["PDH", "VWAP", "200 SMA 1h"]

    def test_regular_session_rejection_can_emit_without_same_candle_detector_label(self):
        engine = ScenarioWatchEngine()
        feature = _feature(
            ts=1782136200,
            idx=163,
            close=322.0,
            upper_wick=1.1,
            lower_wick=0.2,
            body=1.0,
            indicators={"KCU.200 SMA 1h": 322.2},
        )
        level = _level_record(
            ts=1782136200,
            idx=163,
            close_level=322.0,
            pdh=322.1,
            orh=321.95,
            reject=True,
        )

        events = engine.step(feature, level, [])

        assert len(events) == 1
        assert events[0].scenario_type == ScenarioType.REJECTION_WATCH

    def test_ltp_continuation_watch_requires_trend_and_pullback_zone(self):
        engine = ScenarioWatchEngine()
        feature = _feature(
            close=310.0,
            consec_hh=3,
            consec_hl=2,
            indicators={"KCU.21 EMA 5m": 309.9},
        )
        level = _level_record(close_level=310.0, vwap=310.05)

        events = engine.step(feature, level, ["LTP_WATCH"])

        assert len(events) == 1
        assert events[0].scenario_type == ScenarioType.LTP_CONTINUATION_WATCH
        assert events[0].approaching_levels == ["VWAP", "21 EMA 5m"]

    def test_raw_indicator_values_are_used_when_flat_indicators_are_missing(self):
        engine = ScenarioWatchEngine()
        feature = _feature(close=300.0, indicators={})
        level = _level_record(close_level=300.0, pdh=300.05)
        raw = [{
            "name": "KCU",
            "values": {"200 SMA 1h": "299.95", "OR High": "330.00"},
        }]

        events = engine.step(feature, level, ["BOUNCE_WATCH"], raw_indicator_values=raw)

        assert len(events) == 1
        assert events[0].approaching_levels == ["200 SMA 1h", "PDH"]

    def test_scenarios_are_logged_even_without_any_trade_plan_flow(self, tmp_path):
        engine = ScenarioWatchEngine()
        feature = _feature(close=300.0, indicators={"KCU.200 SMA 1h": 300.1})
        level = _level_record(close_level=300.0, pdh=300.05, touch=True)
        path = tmp_path / "scenario_events.jsonl"

        result = engine.run_and_write(
            [feature],
            [level],
            [["BOUNCE_WATCH"]],
            output_path=path,
        )

        assert path.exists()
        assert result.artifacts is not None
        assert result.artifacts.scenario_events_path == path
        loaded = load_scenario_events(path)
        assert len(loaded) == 1
        assert loaded[0].scenario_type == ScenarioType.BOUNCE_WATCH
        assert json.loads(path.read_text().strip())["scenario_type"] == ScenarioType.BOUNCE_WATCH

    def test_run_rejects_length_mismatch(self):
        engine = ScenarioWatchEngine()
        feature = _feature()
        level = _level_record()
        with pytest.raises(ValueError, match="equal length"):
            engine.run([feature], [level], [[], []])
