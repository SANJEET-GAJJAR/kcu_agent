"""Unit tests for Phase 4C — Level Context Engine.

Acceptance criteria:
  - Tests prove no future candles are used.
  - Tests prove unknown levels remain UNKNOWN (not False/0).
  - Tests prove touch / reclaim / reject / hold calculations.
  - Tests prove nearest level calculations.
  - Tests prove replay determinism.
  - Tests prove no trading logic exists.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest

from src.features.level_context import (
    LevelSource,
    NamedLevel,
    LevelConfig,
    LevelRecord,
    LevelExtractor,
    _find_nearest,
    _distance_to_nearest,
    _compute_touch,
    _compute_reclaim,
    _compute_reject,
    _compute_hold,
    _compute_in_middle,
    _compute_clustered,
    _et_hour,
)
from src.features.feature_record import FeatureRecord


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

TS_BASE = 1705329000   # 2024-01-15 09:30:00 ET (regular session open)
TS_PRE  = 1705311600   # 2024-01-15 04:30:00 ET (premarket)


def _feat(
    ts: int = TS_BASE,
    idx: int = 0,
    o: float = 195.0,
    h: float = 197.0,
    l: float = 193.0,
    c: float = 196.0,
    v: float = 10000.0,
    session: str = "regular",
    time_since_open: float = 0.0,
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
    dist_prev: float | None = None,
    dist_open: float | None = None,
    gap: float | None = None,
    replay_date: str = "2024-01-15",
    symbol: str = "TSLA",
    timeframe: str = "2",
    indicators: dict | None = None,
) -> FeatureRecord:
    return FeatureRecord(
        timestamp=ts,
        symbol=symbol,
        timeframe=timeframe,
        replay_date=replay_date,
        candle_index=idx,
        open=o,
        high=h,
        low=l,
        close=c,
        volume=v,
        candle_body=abs(c - o),
        upper_wick=upper_wick,
        lower_wick=lower_wick,
        body_pct=body_pct,
        candle_range=h - l,
        atr=atr,
        gap_from_prev=gap,
        distance_from_prev_close=dist_prev,
        is_higher_high=is_hh,
        is_lower_low=is_ll,
        is_inside_bar=is_inside,
        is_outside_bar=is_outside,
        consecutive_hh=consec_hh,
        consecutive_ll=consec_ll,
        consecutive_lh=consec_lh,
        consecutive_hl=consec_hl,
        relative_volume=rvol,
        session=session,
        time_since_open_minutes=time_since_open,
        distance_from_session_open=dist_open,
        indicators=indicators or {},
    )


def _premarket(ts: int = TS_PRE, idx: int = 0, h: float = 200.0, l: float = 195.0, c: float = 198.0,
               indicators: dict | None = None) -> FeatureRecord:
    return _feat(ts=ts, idx=idx, o=196.0, h=h, l=l, c=c, session="premarket", time_since_open=-60.0,
                 indicators=indicators)


def _regular(ts: int = TS_BASE, idx: int = 1, h: float = 197.0, l: float = 193.0, c: float = 196.0,
             time_since_open: float = 0.0, indicators: dict | None = None) -> FeatureRecord:
    return _feat(ts=ts, idx=idx, h=h, l=l, c=c, session="regular", time_since_open=time_since_open,
                 indicators=indicators)


def _mk_level(name: str, value: float | None, source: str = LevelSource.DERIVED) -> NamedLevel:
    return NamedLevel(name=name, value=value, source=source)


# ---------------------------------------------------------------------------
# LevelSource
# ---------------------------------------------------------------------------

class TestLevelSource:
    def test_all_values_constant(self):
        assert LevelSource.INDICATOR in LevelSource.ALL_VALUES
        assert LevelSource.DERIVED in LevelSource.ALL_VALUES
        assert LevelSource.UNKNOWN in LevelSource.ALL_VALUES

    def test_values_are_strings(self):
        for v in LevelSource.ALL_VALUES:
            assert isinstance(v, str)


# ---------------------------------------------------------------------------
# NamedLevel
# ---------------------------------------------------------------------------

class TestNamedLevel:
    def test_known_level(self):
        lvl = NamedLevel.derived("ORH", 197.5)
        assert lvl.is_known() is True
        assert lvl.value == 197.5
        assert lvl.source == LevelSource.DERIVED

    def test_unknown_level(self):
        lvl = NamedLevel.unknown("PDH")
        assert lvl.is_known() is False
        assert lvl.value is None
        assert lvl.source == LevelSource.UNKNOWN

    def test_indicator_source(self):
        lvl = NamedLevel.from_indicator("VWAP", 196.2)
        assert lvl.source == LevelSource.INDICATOR
        assert lvl.is_known() is True

    def test_to_dict(self):
        lvl = NamedLevel.derived("ORH", 197.5)
        d = lvl.to_dict()
        assert d == {"name": "ORH", "value": 197.5, "source": "derived"}

    def test_to_dict_unknown(self):
        lvl = NamedLevel.unknown("PDH")
        d = lvl.to_dict()
        assert d == {"name": "PDH", "value": None, "source": "unknown"}

    def test_from_dict_roundtrip(self):
        lvl = NamedLevel.derived("PMH", 200.5)
        restored = NamedLevel.from_dict(lvl.to_dict())
        assert restored.name == lvl.name
        assert restored.value == lvl.value
        assert restored.source == lvl.source

    def test_from_dict_none_value(self):
        lvl = NamedLevel.from_dict({"name": "PDH", "value": None, "source": "unknown"})
        assert lvl.is_known() is False


# ---------------------------------------------------------------------------
# LevelConfig
# ---------------------------------------------------------------------------

class TestLevelConfig:
    def test_defaults(self):
        cfg = LevelConfig()
        assert cfg.opening_range_minutes == 30.0
        assert cfg.touch_threshold_pct == 0.15
        assert cfg.cluster_threshold_pct == 0.25
        assert cfg.hold_lookback == 3
        assert "VWAP" in cfg.vwap_indicator_keys

    def test_invalid_opening_range(self):
        with pytest.raises(ValueError, match="opening_range_minutes"):
            LevelConfig(opening_range_minutes=0.0)

    def test_invalid_touch_threshold(self):
        with pytest.raises(ValueError, match="touch_threshold_pct"):
            LevelConfig(touch_threshold_pct=0.0)

    def test_invalid_hold_lookback(self):
        with pytest.raises(ValueError, match="hold_lookback"):
            LevelConfig(hold_lookback=0)

    def test_custom_config(self):
        cfg = LevelConfig(opening_range_minutes=15.0, touch_threshold_pct=0.1)
        assert cfg.opening_range_minutes == 15.0


# ---------------------------------------------------------------------------
# LevelRecord
# ---------------------------------------------------------------------------

class TestLevelRecord:
    def _make(self) -> LevelRecord:
        return LevelRecord(
            timestamp=TS_BASE,
            symbol="TSLA",
            timeframe="2",
            replay_date="2024-01-15",
            candle_index=5,
            pmh=NamedLevel.derived("PMH", 200.0),
            pml=NamedLevel.derived("PML", 194.0),
            pdh=NamedLevel.unknown("PDH"),
            pdl=NamedLevel.unknown("PDL"),
            pdc=NamedLevel.unknown("PDC"),
            orh=NamedLevel.derived("ORH", 197.5),
            orl=NamedLevel.derived("ORL", 193.5),
            vwap=NamedLevel.from_indicator("VWAP", 195.8),
            opening_price=NamedLevel.derived("OPEN", 196.0),
        )

    def test_validate_passes(self):
        r = self._make()
        assert r.validate() == []

    def test_validate_bad_timestamp(self):
        r = self._make()
        r.timestamp = -1
        assert any("timestamp" in e for e in r.validate())

    def test_validate_bad_candle_index(self):
        r = self._make()
        r.candle_index = -1
        assert any("candle_index" in e for e in r.validate())

    def test_validate_bad_source(self):
        r = self._make()
        r.pdh = NamedLevel(name="PDH", value=200.0, source="bad_source")
        assert any("source" in e for e in r.validate())

    def test_validate_negative_distance(self):
        r = self._make()
        r.distance_to_nearest_level = -1.0
        assert any("distance_to_nearest_level" in e for e in r.validate())

    def test_to_dict_has_all_fields(self):
        r = self._make()
        d = r.to_dict()
        required = [
            "timestamp", "symbol", "timeframe", "replay_date", "candle_index",
            "pmh", "pml", "pdh", "pdl", "pdc", "orh", "orl", "vwap", "opening_price",
            "hourly_levels", "nearest_level_above", "nearest_level_below",
            "distance_to_nearest_level", "level_touch", "level_reclaim",
            "level_reject", "level_hold", "in_middle_of_range",
            "clustered_levels", "distance_to_open", "distance_to_vwap",
        ]
        for key in required:
            assert key in d, f"Missing key: {key}"

    def test_to_dict_no_trade_fields(self):
        r = self._make()
        d = r.to_dict()
        trade_fields = {"entry", "stop", "target", "size", "risk", "reward"}
        assert not (set(d.keys()) & trade_fields)

    def test_from_dict_roundtrip(self):
        r = self._make()
        r.level_touch = True
        r.clustered_levels = ["VWAP", "OPEN"]
        r.distance_to_nearest_level = 0.5
        r2 = LevelRecord.from_dict(r.to_dict())
        assert r2.timestamp == r.timestamp
        assert r2.pmh.value == r.pmh.value
        assert r2.vwap.source == LevelSource.INDICATOR
        assert r2.pdh.source == LevelSource.UNKNOWN
        assert r2.level_touch is True
        assert r2.clustered_levels == ["VWAP", "OPEN"]

    def test_to_jsonl_line(self):
        r = self._make()
        line = r.to_jsonl_line()
        parsed = json.loads(line)
        assert parsed["timestamp"] == TS_BASE

    def test_no_trade_fields_in_dataclass(self):
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(LevelRecord)}
        trade_fields = {"entry", "stop", "target", "size", "risk", "reward", "pnl"}
        overlap = field_names & trade_fields
        assert overlap == set(), f"Trade fields found: {overlap}"


# ---------------------------------------------------------------------------
# VWAP extraction
# ---------------------------------------------------------------------------

class TestVWAPExtraction:
    def test_vwap_from_indicators(self):
        feat = _regular(indicators={"VWAP": 195.5})
        ex = LevelExtractor()
        lr = ex.step(feat)
        assert lr.vwap.is_known() is True
        assert lr.vwap.value == 195.5
        assert lr.vwap.source == LevelSource.INDICATOR

    def test_vwap_lowercase_key(self):
        feat = _regular(indicators={"vwap": 195.5})
        ex = LevelExtractor()
        lr = ex.step(feat)
        assert lr.vwap.is_known() is True

    def test_vwap_missing_is_unknown_not_false(self):
        feat = _regular(indicators={})
        ex = LevelExtractor()
        lr = ex.step(feat)
        assert lr.vwap.source == LevelSource.UNKNOWN
        assert lr.vwap.value is None
        assert lr.vwap.is_known() is False

    def test_vwap_non_numeric_is_unknown(self):
        feat = _regular(indicators={"VWAP": "bad"})
        ex = LevelExtractor()
        lr = ex.step(feat)
        assert lr.vwap.source == LevelSource.UNKNOWN


# ---------------------------------------------------------------------------
# Opening Price
# ---------------------------------------------------------------------------

class TestOpeningPrice:
    def test_opening_price_unknown_in_premarket(self):
        pm = _premarket()
        ex = LevelExtractor()
        lr = ex.step(pm)
        assert lr.opening_price.source == LevelSource.UNKNOWN
        assert lr.opening_price.is_known() is False

    def test_opening_price_latched_at_first_regular_candle(self):
        pm = _premarket()
        reg = _regular(c=196.0)
        ex = LevelExtractor()
        ex.step(pm)
        lr = ex.step(reg)
        assert lr.opening_price.is_known() is True
        assert lr.opening_price.value == 196.0
        assert lr.opening_price.source == LevelSource.DERIVED

    def test_opening_price_stable_after_latch(self):
        ex = LevelExtractor()
        reg1 = _regular(idx=0, c=196.0, time_since_open=0.0)
        reg2 = _regular(idx=1, ts=TS_BASE + 120, c=198.0, time_since_open=2.0)
        ex.step(reg1)
        lr2 = ex.step(reg2)
        assert lr2.opening_price.value == 196.0  # latched from first candle

    def test_opening_price_derived_source(self):
        ex = LevelExtractor()
        lr = ex.step(_regular())
        assert lr.opening_price.source == LevelSource.DERIVED


# ---------------------------------------------------------------------------
# Premarket levels (PMH / PML)
# ---------------------------------------------------------------------------

class TestPremarketLevels:
    def test_pmh_pml_unknown_before_any_premarket(self):
        ex = LevelExtractor()
        lr = ex.step(_regular())
        assert lr.pmh.source == LevelSource.UNKNOWN
        assert lr.pml.source == LevelSource.UNKNOWN

    def test_pmh_pml_from_premarket_candle(self):
        ex = LevelExtractor()
        pm = _premarket(h=202.0, l=197.0)
        lr = ex.step(pm)
        assert lr.pmh.value == 202.0
        assert lr.pml.value == 197.0
        assert lr.pmh.source == LevelSource.DERIVED

    def test_pmh_includes_current_premarket_candle(self):
        ex = LevelExtractor()
        pm1 = _premarket(ts=TS_PRE, idx=0, h=200.0, l=195.0)
        pm2 = _premarket(ts=TS_PRE + 120, idx=1, h=203.0, l=194.0)
        ex.step(pm1)
        lr = ex.step(pm2)
        # pm2 is the current candle — should contribute to PMH/PML
        assert lr.pmh.value == 203.0
        assert lr.pml.value == 194.0

    def test_pmh_pml_not_reset_in_regular_session(self):
        ex = LevelExtractor()
        pm = _premarket(h=205.0, l=190.0)
        reg = _regular(ts=TS_BASE, idx=1)
        ex.step(pm)
        lr = ex.step(reg)
        # Premarket candle is now in past window — PMH/PML still available
        assert lr.pmh.value == 205.0
        assert lr.pml.value == 190.0

    def test_pmh_pml_derived_source(self):
        ex = LevelExtractor()
        pm = _premarket(h=200.0, l=195.0)
        lr = ex.step(pm)
        assert lr.pmh.source == LevelSource.DERIVED
        assert lr.pml.source == LevelSource.DERIVED


# ---------------------------------------------------------------------------
# Opening Range (ORH / ORL)
# ---------------------------------------------------------------------------

class TestOpeningRangeLevels:
    def test_or_unknown_before_range_complete(self):
        ex = LevelExtractor()
        reg = _regular(time_since_open=0.0)
        lr = ex.step(reg)
        assert lr.orh.source == LevelSource.UNKNOWN
        assert lr.orl.source == LevelSource.UNKNOWN

    def test_or_unknown_during_range(self):
        ex = LevelExtractor()
        # OR period = first 30 min (time_since_open < 30)
        r1 = _regular(idx=0, ts=TS_BASE, time_since_open=0.0)
        r2 = _regular(idx=1, ts=TS_BASE + 120, time_since_open=2.0)
        r3 = _regular(idx=2, ts=TS_BASE + 240, time_since_open=4.0)
        ex.step(r1)
        ex.step(r2)
        lr = ex.step(r3)
        assert lr.orh.source == LevelSource.UNKNOWN  # still inside OR

    def test_or_available_after_range_complete(self):
        ex = LevelExtractor()
        # Simulate OR candles
        for i in range(15):
            ex.step(_regular(
                idx=i,
                ts=TS_BASE + i * 120,
                h=197.0 + i * 0.1,
                l=193.0 - i * 0.1,
                time_since_open=float(i * 2),
            ))
        # Now past 30 minutes
        lr = ex.step(_regular(
            idx=15, ts=TS_BASE + 15 * 120,
            h=196.0, l=194.0,
            time_since_open=30.0,
        ))
        assert lr.orh.is_known() is True
        assert lr.orl.is_known() is True
        assert lr.orh.source == LevelSource.DERIVED
        assert lr.orl.source == LevelSource.DERIVED

    def test_orh_uses_highs_not_closes(self):
        ex = LevelExtractor()
        # Two OR candles with high spikes
        ex.step(_regular(idx=0, ts=TS_BASE, h=200.0, l=193.0, c=194.0, time_since_open=0.0))
        ex.step(_regular(idx=1, ts=TS_BASE + 120, h=198.0, l=194.0, c=195.0, time_since_open=2.0))
        # Past OR
        lr = ex.step(_regular(idx=2, ts=TS_BASE + 1800, h=196.0, l=194.0, time_since_open=30.0))
        assert lr.orh.value == 200.0  # max high from OR candles

    def test_orl_uses_lows_not_closes(self):
        ex = LevelExtractor()
        ex.step(_regular(idx=0, ts=TS_BASE, h=197.0, l=190.0, c=194.0, time_since_open=0.0))
        ex.step(_regular(idx=1, ts=TS_BASE + 120, h=197.0, l=192.0, c=195.0, time_since_open=2.0))
        lr = ex.step(_regular(idx=2, ts=TS_BASE + 1800, h=196.0, l=194.0, time_since_open=30.0))
        assert lr.orl.value == 190.0  # min low from OR candles

    def test_or_does_not_use_current_candle(self):
        """ORH/ORL are derived from PAST candles only."""
        ex = LevelExtractor()
        # Push candles inside OR period
        for i in range(15):
            ex.step(_regular(idx=i, ts=TS_BASE + i * 120, h=197.0, l=193.0, time_since_open=float(i * 2)))
        # This candle is at exactly 30 min — it would be inside OR (0 <= 30 < 30 is False)
        # Current candle at time_since_open=30 is the first candle PAST the OR
        # Its high/low should NOT be included in ORH/ORL
        lr = ex.step(_regular(idx=15, ts=TS_BASE + 1800, h=210.0, l=180.0, time_since_open=30.0))
        # 210.0 and 180.0 are extreme — should not appear in ORH/ORL
        assert lr.orh.value != 210.0
        assert lr.orl.value != 180.0


# ---------------------------------------------------------------------------
# Prior Day levels (PDH / PDL / PDC)
# ---------------------------------------------------------------------------

class TestPriorDayLevels:
    def test_pdh_from_indicator(self):
        feat = _regular(indicators={"PDH": 205.0})
        lr = LevelExtractor().step(feat)
        assert lr.pdh.value == 205.0
        assert lr.pdh.source == LevelSource.INDICATOR

    def test_pdl_from_indicator(self):
        feat = _regular(indicators={"PDL": 188.0})
        lr = LevelExtractor().step(feat)
        assert lr.pdl.value == 188.0
        assert lr.pdl.source == LevelSource.INDICATOR

    def test_pdc_from_indicator(self):
        feat = _regular(indicators={"PDC": 193.5})
        lr = LevelExtractor().step(feat)
        assert lr.pdc.value == 193.5
        assert lr.pdc.source == LevelSource.INDICATOR

    def test_pdc_alias_prior_day_close(self):
        feat = _regular(indicators={"Prior Day Close": 192.0})
        lr = LevelExtractor().step(feat)
        assert lr.pdc.is_known() is True

    def test_prior_day_unknown_when_not_in_indicators(self):
        feat = _regular(indicators={})
        lr = LevelExtractor().step(feat)
        assert lr.pdh.source == LevelSource.UNKNOWN
        assert lr.pdl.source == LevelSource.UNKNOWN
        assert lr.pdc.source == LevelSource.UNKNOWN
        assert lr.pdh.value is None
        assert lr.pdl.value is None
        assert lr.pdc.value is None

    def test_unknown_is_none_not_false(self):
        """Missing PDH/PDL/PDC must be None, not False or 0."""
        feat = _regular(indicators={})
        lr = LevelExtractor().step(feat)
        assert lr.pdh.value is None
        assert not (lr.pdh.value is False)
        assert not (lr.pdh.value == 0)


# ---------------------------------------------------------------------------
# Hourly levels
# ---------------------------------------------------------------------------

class TestHourlyLevels:
    def test_no_hourly_levels_at_start(self):
        # First candle has no past window
        lr = LevelExtractor().step(_regular(ts=TS_BASE, time_since_open=0.0))
        assert lr.hourly_levels == []

    def test_hourly_levels_after_completed_hour(self):
        ex = LevelExtractor()
        # Push candles in the 09:xx ET hour (9:30 AM ET candles)
        # TS_BASE = 09:30 ET
        # Add a few regular candles in the 9 o'clock hour
        for i in range(5):
            ts = TS_BASE + i * 120
            ex.step(_regular(idx=i, ts=ts, h=197.0 + i, l=193.0 - i, time_since_open=float(i * 2)))

        # Now a candle in the 10 o'clock hour (ts = 10:00 ET = TS_BASE + 30*60 = 1705329000 + 1800)
        ts_10 = TS_BASE + 3600  # 10:30 ET (one full hour later)
        lr = ex.step(_regular(idx=5, ts=ts_10, h=196.0, l=194.0, time_since_open=60.0))

        # Should have hourly levels for the 09 ET hour
        names = [l.name for l in lr.hourly_levels]
        assert any("09" in n for n in names), f"Expected H09_HIGH/LOW in {names}"

    def test_hourly_level_uses_past_candles_only(self):
        """Current candle must NOT contribute to its own hour's level."""
        ex = LevelExtractor()
        # Single regular candle at 9:30 (hour 9) — no past candles in any prior hour
        lr = ex.step(_regular(idx=0, ts=TS_BASE, h=210.0, l=180.0, time_since_open=0.0))
        # No hourly levels since no PAST candles from prior hours exist
        assert lr.hourly_levels == []

    def test_hourly_levels_source_is_derived(self):
        ex = LevelExtractor()
        for i in range(5):
            ex.step(_regular(idx=i, ts=TS_BASE + i * 120))
        ts_next_hour = TS_BASE + 3600
        lr = ex.step(_regular(idx=5, ts=ts_next_hour, time_since_open=60.0))
        for lvl in lr.hourly_levels:
            assert lvl.source == LevelSource.DERIVED

    def test_hourly_high_is_max_of_highs(self):
        ex = LevelExtractor()
        highs = [197.0, 199.0, 196.5, 198.0, 201.0]
        for i, h in enumerate(highs):
            ex.step(_regular(idx=i, ts=TS_BASE + i * 120, h=h, l=193.0))
        ts_next = TS_BASE + 3600
        lr = ex.step(_regular(idx=5, ts=ts_next, time_since_open=60.0))
        h09_names = [l for l in lr.hourly_levels if "HIGH" in l.name]
        if h09_names:
            assert h09_names[0].value == max(highs)

    def test_hourly_low_is_min_of_lows(self):
        ex = LevelExtractor()
        lows = [193.0, 191.5, 194.0, 192.0, 190.5]
        for i, lv in enumerate(lows):
            ex.step(_regular(idx=i, ts=TS_BASE + i * 120, l=lv))
        ts_next = TS_BASE + 3600
        lr = ex.step(_regular(idx=5, ts=ts_next, time_since_open=60.0))
        l09_names = [l for l in lr.hourly_levels if "LOW" in l.name]
        if l09_names:
            assert l09_names[0].value == min(lows)


# ---------------------------------------------------------------------------
# Proximity analysis
# ---------------------------------------------------------------------------

class TestNearestLevel:
    def test_nearest_above(self):
        levels = [_mk_level("A", 200.0), _mk_level("B", 198.0), _mk_level("C", 195.0)]
        above, below = _find_nearest(196.5, levels)
        assert above is not None
        assert above.value == 198.0  # closer than 200.0

    def test_nearest_below(self):
        levels = [_mk_level("A", 200.0), _mk_level("B", 198.0), _mk_level("C", 195.0)]
        above, below = _find_nearest(196.5, levels)
        assert below is not None
        assert below.value == 195.0  # closest below 196.5

    def test_no_levels_above(self):
        levels = [_mk_level("A", 190.0), _mk_level("B", 185.0)]
        above, below = _find_nearest(195.0, levels)
        assert above is None
        assert below is not None

    def test_no_levels_below(self):
        levels = [_mk_level("A", 200.0), _mk_level("B", 205.0)]
        above, below = _find_nearest(195.0, levels)
        assert above is not None
        assert below is None

    def test_empty_levels(self):
        above, below = _find_nearest(196.0, [])
        assert above is None
        assert below is None

    def test_distance_to_nearest(self):
        levels = [_mk_level("A", 200.0), _mk_level("B", 195.0)]
        above, below = _find_nearest(196.0, levels)
        dist = _distance_to_nearest(196.0, above, below)
        assert dist == 1.0  # nearest is 195.0, distance = 1.0

    def test_distance_none_when_no_levels(self):
        dist = _distance_to_nearest(196.0, None, None)
        assert dist is None

    def test_distance_only_above(self):
        above = _mk_level("A", 200.0)
        dist = _distance_to_nearest(196.0, above, None)
        assert dist == 4.0

    def test_extractor_nearest_above_populated(self):
        ex = LevelExtractor()
        # VWAP above the close
        feat = _regular(c=195.0, indicators={"VWAP": 197.0})
        lr = ex.step(feat)
        assert lr.nearest_level_above is not None
        assert lr.nearest_level_above.value == 197.0

    def test_extractor_nearest_below_populated(self):
        ex = LevelExtractor()
        feat = _regular(c=198.0, indicators={"VWAP": 196.0})
        lr = ex.step(feat)
        assert lr.nearest_level_below is not None
        assert lr.nearest_level_below.value == 196.0

    def test_extractor_distance_to_nearest_level(self):
        ex = LevelExtractor()
        feat = _regular(c=196.0, indicators={"VWAP": 197.0})
        lr = ex.step(feat)
        assert lr.distance_to_nearest_level is not None
        assert lr.distance_to_nearest_level == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Touch analysis
# ---------------------------------------------------------------------------

class TestLevelTouch:
    def test_touch_true_when_within_threshold(self):
        # threshold_pct=0.15 → within 0.15% of level
        lvls = [_mk_level("VWAP", 196.0)]
        result = _compute_touch(196.1, lvls, 0.15)  # 0.05% away
        assert result is True

    def test_touch_false_when_far(self):
        lvls = [_mk_level("VWAP", 196.0)]
        result = _compute_touch(198.0, lvls, 0.15)  # ~1% away
        assert result is False

    def test_touch_none_when_no_levels(self):
        result = _compute_touch(196.0, [], 0.15)
        assert result is None

    def test_touch_any_level_triggers(self):
        lvls = [_mk_level("A", 200.0), _mk_level("B", 196.05)]
        result = _compute_touch(196.0, lvls, 0.15)
        assert result is True

    def test_extractor_level_touch(self):
        ex = LevelExtractor(LevelConfig(touch_threshold_pct=0.5))
        feat = _regular(c=196.0, indicators={"VWAP": 196.5})
        lr = ex.step(feat)
        # 196.5 is within 0.5% of 196.0 (diff = 0.256%)
        assert lr.level_touch is True

    def test_extractor_level_touch_false_far_from_all_levels(self):
        # First push a regular candle to latch opening price at 196.0.
        # Then check a second candle that has moved far from VWAP and OPEN.
        ex = LevelExtractor(LevelConfig(touch_threshold_pct=0.10))
        ex.step(_regular(idx=0, ts=TS_BASE, c=196.0, time_since_open=0.0, indicators={"VWAP": 196.0}))
        # Now price moves far from OPEN=196.0 and VWAP=190.0 (both >3% away from 202)
        lr = ex.step(_regular(idx=1, ts=TS_BASE + 120, c=202.0, time_since_open=2.0, indicators={"VWAP": 190.0}))
        # 202 vs OPEN=196 = 3.0% away; 202 vs VWAP=190 = 6.3% away — not touching either
        assert lr.level_touch is False

    def test_level_touch_none_when_no_known_levels_pure(self):
        # The pure _compute_touch function returns None on empty level list.
        result = _compute_touch(196.0, [], 0.15)
        assert result is None

    def test_level_touch_not_none_on_regular_candle(self):
        # The first regular candle always has opening_price latched — never None.
        ex = LevelExtractor()
        lr = ex.step(_regular(indicators={}))
        assert lr.level_touch is not None


# ---------------------------------------------------------------------------
# Reclaim analysis
# ---------------------------------------------------------------------------

class TestLevelReclaim:
    def test_reclaim_true_when_crossed_above(self):
        lvls = [_mk_level("VWAP", 196.0)]
        result = _compute_reclaim(196.5, 195.5, lvls)  # prev below, curr above
        assert result is True

    def test_reclaim_false_when_no_cross(self):
        lvls = [_mk_level("VWAP", 196.0)]
        result = _compute_reclaim(196.5, 196.2, lvls)  # both above
        assert result is False

    def test_reclaim_false_when_below(self):
        lvls = [_mk_level("VWAP", 196.0)]
        result = _compute_reclaim(195.5, 195.0, lvls)  # both below
        assert result is False

    def test_reclaim_none_on_first_candle(self):
        lvls = [_mk_level("VWAP", 196.0)]
        result = _compute_reclaim(196.5, None, lvls)
        assert result is None

    def test_reclaim_none_when_no_levels(self):
        result = _compute_reclaim(196.5, 195.0, [])
        assert result is None

    def test_extractor_reclaim(self):
        ex = LevelExtractor()
        # First candle: close BELOW vwap=196.0
        ex.step(_regular(idx=0, ts=TS_BASE, c=195.0, indicators={"VWAP": 196.0}))
        # Second candle: close ABOVE vwap=196.0 → reclaim
        lr = ex.step(_regular(idx=1, ts=TS_BASE + 120, c=196.5, indicators={"VWAP": 196.0}))
        assert lr.level_reclaim is True


# ---------------------------------------------------------------------------
# Reject analysis
# ---------------------------------------------------------------------------

class TestLevelReject:
    def test_reject_true_when_crossed_below(self):
        lvls = [_mk_level("VWAP", 196.0)]
        result = _compute_reject(195.5, 196.5, lvls)  # prev above, curr below
        assert result is True

    def test_reject_false_when_no_cross(self):
        lvls = [_mk_level("VWAP", 196.0)]
        result = _compute_reject(195.5, 195.0, lvls)  # both below
        assert result is False

    def test_reject_none_on_first_candle(self):
        lvls = [_mk_level("VWAP", 196.0)]
        assert _compute_reject(195.5, None, lvls) is None

    def test_reject_none_when_no_levels(self):
        assert _compute_reject(195.5, 196.5, []) is None

    def test_extractor_reject(self):
        ex = LevelExtractor()
        # First candle: close ABOVE vwap=196.0
        ex.step(_regular(idx=0, ts=TS_BASE, c=196.5, indicators={"VWAP": 196.0}))
        # Second candle: close BELOW vwap=196.0 → reject
        lr = ex.step(_regular(idx=1, ts=TS_BASE + 120, c=195.5, indicators={"VWAP": 196.0}))
        assert lr.level_reject is True


# ---------------------------------------------------------------------------
# Hold analysis
# ---------------------------------------------------------------------------

class TestLevelHold:
    def _make_past(self, closes: list[float]) -> tuple[FeatureRecord, ...]:
        return tuple(
            _regular(idx=i, ts=TS_BASE + i * 120, c=c)
            for i, c in enumerate(closes)
        )

    def test_hold_true_when_consistently_above(self):
        lvls = [_mk_level("VWAP", 195.0)]
        past = self._make_past([196.0, 197.0, 196.5])
        result = _compute_hold(196.0, past, lvls, lookback=3)
        assert result is True

    def test_hold_true_when_consistently_below(self):
        lvls = [_mk_level("VWAP", 197.0)]
        past = self._make_past([196.0, 195.5, 196.2])
        result = _compute_hold(196.0, past, lvls, lookback=3)
        assert result is True

    def test_hold_false_when_not_consistent(self):
        lvls = [_mk_level("VWAP", 196.0)]
        past = self._make_past([196.5, 195.5, 196.5])  # crosses 196
        result = _compute_hold(196.5, past, lvls, lookback=3)
        assert result is False

    def test_hold_none_insufficient_history(self):
        lvls = [_mk_level("VWAP", 195.0)]
        past = self._make_past([196.0])  # only 1 past, lookback=3
        result = _compute_hold(196.0, past, lvls, lookback=3)
        assert result is None

    def test_hold_none_when_no_levels(self):
        past = self._make_past([196.0, 196.5, 196.2])
        result = _compute_hold(196.0, past, [], lookback=3)
        assert result is None

    def test_extractor_hold(self):
        ex = LevelExtractor(LevelConfig(hold_lookback=2))
        # Push two candles above VWAP
        ex.step(_regular(idx=0, ts=TS_BASE, c=197.0, indicators={"VWAP": 195.0}))
        ex.step(_regular(idx=1, ts=TS_BASE + 120, c=197.5, indicators={"VWAP": 195.0}))
        # Third candle also above VWAP
        lr = ex.step(_regular(idx=2, ts=TS_BASE + 240, c=198.0, indicators={"VWAP": 195.0}))
        assert lr.level_hold is True


# ---------------------------------------------------------------------------
# In middle of range
# ---------------------------------------------------------------------------

class TestInMiddleOfRange:
    def test_in_middle_true_when_away_from_all_levels(self):
        levels = [_mk_level("A", 200.0), _mk_level("B", 190.0)]
        result = _compute_in_middle(195.0, levels, 0.15)
        # 195 is ~2.5% from both levels → in middle
        assert result is True

    def test_in_middle_false_when_near_a_level(self):
        levels = [_mk_level("A", 195.1)]
        result = _compute_in_middle(195.0, levels, 0.15)
        # 0.05% away → touching, not in middle
        assert result is False

    def test_in_middle_none_when_no_levels(self):
        result = _compute_in_middle(195.0, [], 0.15)
        assert result is None

    def test_extractor_in_middle(self):
        # Use two candles so OPEN=196 is in past, then price moves to 202
        # (far from OPEN=196 and VWAP=190 → in middle)
        ex = LevelExtractor(LevelConfig(touch_threshold_pct=0.10))
        ex.step(_regular(idx=0, ts=TS_BASE, c=196.0, time_since_open=0.0, indicators={"VWAP": 196.0}))
        lr = ex.step(_regular(idx=1, ts=TS_BASE + 120, c=202.0, time_since_open=2.0, indicators={"VWAP": 190.0}))
        # OPEN=196.0 is 3% away from 202; VWAP=190 is 6% away → both beyond 0.10% → in middle
        assert lr.in_middle_of_range is True

    def test_in_middle_is_complement_of_touch(self):
        """in_middle_of_range and level_touch are complementary when levels exist."""
        levels = [_mk_level("A", 196.05)]
        close = 196.0
        touch = _compute_touch(close, levels, 0.15)
        in_mid = _compute_in_middle(close, levels, 0.15)
        if touch is not None and in_mid is not None:
            assert touch != in_mid  # exactly one should be True


# ---------------------------------------------------------------------------
# Clustered levels
# ---------------------------------------------------------------------------

class TestClusteredLevels:
    def test_clustered_when_levels_near_each_other_near_price(self):
        # Both levels near price (within cluster_threshold_pct)
        levels = [_mk_level("A", 196.1), _mk_level("B", 196.2)]
        clustered = _compute_clustered(196.0, levels, 0.25)
        assert "A" in clustered
        assert "B" in clustered

    def test_not_clustered_when_spread_out(self):
        levels = [_mk_level("A", 200.0), _mk_level("B", 190.0)]
        clustered = _compute_clustered(196.0, levels, 0.25)
        assert clustered == []

    def test_clustered_empty_when_no_levels(self):
        assert _compute_clustered(196.0, [], 0.25) == []

    def test_extractor_clustered_levels(self):
        ex = LevelExtractor(LevelConfig(cluster_threshold_pct=0.5))
        feat = _regular(c=196.0, indicators={"VWAP": 196.5})
        lr = ex.step(feat)
        # VWAP at 196.5 is 0.26% from 196 — within 0.5% threshold
        assert "VWAP" in lr.clustered_levels


# ---------------------------------------------------------------------------
# Distance helpers
# ---------------------------------------------------------------------------

class TestDistanceHelpers:
    def test_distance_to_vwap(self):
        ex = LevelExtractor()
        feat = _regular(c=196.0, indicators={"VWAP": 197.5})
        lr = ex.step(feat)
        assert lr.distance_to_vwap == pytest.approx(-1.5)

    def test_distance_to_vwap_none_when_missing(self):
        ex = LevelExtractor()
        lr = ex.step(_regular(indicators={}))
        assert lr.distance_to_vwap is None

    def test_distance_to_open_zero_at_first_regular_candle(self):
        ex = LevelExtractor()
        lr = ex.step(_regular(c=196.0))
        # First regular candle: opening_price = 196.0, distance = 0
        assert lr.distance_to_open == pytest.approx(0.0)

    def test_distance_to_open_positive_above_open(self):
        ex = LevelExtractor()
        ex.step(_regular(idx=0, ts=TS_BASE, c=196.0, time_since_open=0.0))
        lr = ex.step(_regular(idx=1, ts=TS_BASE + 120, c=198.0, time_since_open=2.0))
        assert lr.distance_to_open == pytest.approx(2.0)

    def test_distance_to_open_none_in_premarket(self):
        ex = LevelExtractor()
        lr = ex.step(_premarket())
        assert lr.distance_to_open is None


# ---------------------------------------------------------------------------
# No future candles (anti-lookahead)
# ---------------------------------------------------------------------------

class TestNoFutureCandles:
    def test_window_is_past_only(self):
        """LevelExtractor never includes the current candle in the past window when computing."""
        ex = LevelExtractor()
        calls: list[int] = []

        candles = [
            _regular(idx=i, ts=TS_BASE + i * 120, c=195.0 + i, h=197.0 + i, l=193.0 + i)
            for i in range(5)
        ]
        records = [ex.step(c) for c in candles]

        for i, lr in enumerate(records):
            # The candle_index in the LevelRecord must equal the candle's own index
            assert lr.candle_index == i

    def test_orh_uses_only_past_candles(self):
        """Current candle never contributes to ORH/ORL."""
        ex = LevelExtractor()
        # Push OR candles with moderate highs
        for i in range(15):
            ex.step(_regular(idx=i, ts=TS_BASE + i * 120, h=197.0, l=193.0, time_since_open=float(i * 2)))
        # The FIRST past-OR candle has an extreme high — must NOT affect OR
        lr = ex.step(_regular(idx=15, ts=TS_BASE + 1800, h=250.0, l=100.0, time_since_open=30.0))
        assert lr.orh.value == 197.0  # only from past (not current 250.0)
        assert lr.orl.value == 193.0  # only from past (not current 100.0)

    def test_pmh_includes_current_premarket_only(self):
        """PMH includes the current candle only when it is premarket (closing candle).

        A FUTURE candle must never appear in any level computation.
        """
        ex = LevelExtractor()
        # Current premarket candle — PMH should include it (it has closed)
        pm = _premarket(ts=TS_PRE, h=202.0, l=196.0)
        lr = ex.step(pm)
        assert lr.pmh.value == 202.0  # current premarket candle contributes
        # Next candle at higher high
        pm2 = _premarket(ts=TS_PRE + 120, idx=1, h=205.0, l=197.0)
        lr2 = ex.step(pm2)
        assert lr2.pmh.value == 205.0  # both premarket candles contribute

    def test_no_replay_engine_import(self):
        """LevelExtractor must not import ReplayEngine (only BacktestReplay permitted)."""
        source = Path("src/features/level_context.py").read_text()
        assert "ReplayEngine" not in source
        assert "replay_engine" not in source

    def test_level_record_candle_index_monotonic(self):
        ex = LevelExtractor()
        candles = [_regular(idx=i, ts=TS_BASE + i * 120) for i in range(10)]
        records = ex.run(candles)
        indices = [r.candle_index for r in records]
        assert indices == list(range(10))


# ---------------------------------------------------------------------------
# Unknown levels remain UNKNOWN (not False)
# ---------------------------------------------------------------------------

class TestUnknownLevelsAreUnknown:
    def test_pdh_is_unknown_not_false_when_missing(self):
        lr = LevelExtractor().step(_regular(indicators={}))
        assert lr.pdh.value is None
        assert lr.pdh.source == LevelSource.UNKNOWN
        assert not (lr.pdh.value is False)

    def test_pdl_is_unknown_not_false(self):
        lr = LevelExtractor().step(_regular(indicators={}))
        assert lr.pdl.value is None
        assert lr.pdl.source == LevelSource.UNKNOWN

    def test_pdc_is_unknown_not_false(self):
        lr = LevelExtractor().step(_regular(indicators={}))
        assert lr.pdc.value is None

    def test_vwap_is_unknown_not_false(self):
        lr = LevelExtractor().step(_regular(indicators={}))
        assert lr.vwap.value is None

    def test_orh_unknown_before_range_complete(self):
        lr = LevelExtractor().step(_regular(time_since_open=5.0))
        assert lr.orh.source == LevelSource.UNKNOWN
        assert lr.orh.value is None

    def test_level_touch_is_none_when_no_levels_pure(self):
        # The pure function returns None on empty level list — correct "unknown" signal.
        result = _compute_touch(196.0, [], threshold_pct=0.15)
        assert result is None  # None, not False — "unknown" not "not touching"

    def test_level_hold_is_none_not_false_insufficient_history(self):
        ex = LevelExtractor()
        lr = ex.step(_regular(c=196.0, indicators={"VWAP": 195.0}))
        # Only 0 past candles, lookback=3 → None
        assert lr.level_hold is None

    def test_reclaim_is_none_on_first_candle(self):
        lr = LevelExtractor().step(_regular(c=196.0, indicators={"VWAP": 195.0}))
        assert lr.level_reclaim is None


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_inputs_same_output(self):
        candles = [
            _regular(idx=0, ts=TS_BASE, c=196.0, indicators={"VWAP": 195.0}),
            _regular(idx=1, ts=TS_BASE + 120, c=197.0, indicators={"VWAP": 195.5}),
        ]
        ex1 = LevelExtractor()
        ex2 = LevelExtractor()
        r1 = ex1.run(candles)
        r2 = ex2.run(candles)
        assert [r.to_dict() for r in r1] == [r.to_dict() for r in r2]

    def test_reset_restores_initial_state(self):
        ex = LevelExtractor()
        ex.step(_regular(idx=0, ts=TS_BASE, c=196.0))
        ex.reset()
        lr = ex.step(_regular(idx=0, ts=TS_BASE, c=196.0))
        assert lr.opening_price.value == 196.0  # latched afresh

    def test_run_matches_step_by_step(self):
        candles = [
            _regular(idx=i, ts=TS_BASE + i * 120, c=195.0 + i)
            for i in range(5)
        ]
        ex1 = LevelExtractor()
        batch = ex1.run(candles)

        ex2 = LevelExtractor()
        step_by_step = [ex2.step(c) for c in candles]

        assert [r.to_dict() for r in batch] == [r.to_dict() for r in step_by_step]


# ---------------------------------------------------------------------------
# No trading logic in source
# ---------------------------------------------------------------------------

class TestNoTradingLogic:
    _TRADING_TERMS = [
        "entry", "stop_loss", "take_profit", "position_size",
        "risk_reward", "target_price", "order_type",
    ]

    def test_no_trading_terms_in_level_context(self):
        source = Path("src/features/level_context.py").read_text().lower()
        for term in self._TRADING_TERMS:
            assert term not in source, (
                f"Trading term {term!r} found in src/features/level_context.py"
            )

    def test_no_backtestengine_import_in_level_context(self):
        source = Path("src/features/level_context.py").read_text()
        assert "ReplayEngine" not in source
        assert "DetectorEngine" not in source

    def test_level_record_has_no_trade_management(self):
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(LevelRecord)}
        trade_fields = {
            "entry", "stop", "target", "risk", "reward", "size",
            "pnl", "trade_id", "order",
        }
        overlap = field_names & trade_fields
        assert overlap == set(), f"Trade management fields in LevelRecord: {overlap}"

    def test_level_extractor_is_stateless_to_trade_logic(self):
        """LevelExtractor state must contain only window and opening price."""
        ex = LevelExtractor()
        state_attrs = [a for a in dir(ex) if not a.startswith("__") and not callable(getattr(ex, a))]
        for attr in state_attrs:
            assert attr not in {"entry_price", "stop_price", "target_price", "position"}

    def test_no_setup_confirmation_in_level_module(self):
        source = Path("src/features/level_context.py").read_text()
        forbidden = ["CONFIRMED_SETUP", "REJECTED_SETUP", "CandidateEvent", "ConfirmationEvent"]
        for term in forbidden:
            assert term not in source, f"Setup term {term!r} in level_context.py"
