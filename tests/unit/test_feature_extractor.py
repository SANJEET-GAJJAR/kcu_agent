"""Unit tests for Phase 3 feature extraction.

All tests use BacktestReplay — ReplayEngine is never imported here.
"""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from typing import Any

from src.collector.candle_schema import CandleSnapshot
from src.collector.candle_record import CandleRecord, build_record
from src.collector.jsonl_store import JsonlStore
from src.engine.backtest_replay import BacktestReplay
from src.features.feature_config import FeatureConfig
from src.features.feature_record import FeatureRecord
from src.features.rolling_window import RollingWindow
from src.features import candle_features as cf
from src.features.extractor import FeatureExtractor


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

# 2024-01-15 EST (UTC-5)
# 04:00 ET = 09:00 UTC = ts 1705312200 ... let me compute properly
# 2024-01-15 09:30 ET = 14:30 UTC
# Python: from datetime import datetime; from zoneinfo import ZoneInfo
# datetime(2024,1,15,9,30,tzinfo=ZoneInfo("America/New_York")).timestamp() = 1705329000
TS_PREMARKET   = 1705312200   # 2024-01-15 04:30 ET (premarket)
TS_930         = 1705329000   # 2024-01-15 09:30 ET (regular open)
TS_932         = 1705329120   # 09:32 ET
TS_934         = 1705329240   # 09:34 ET
TS_936         = 1705329360   # 09:36 ET
TS_938         = 1705329480   # 09:38 ET
TS_CLOSE       = 1705356000   # 2024-01-15 16:00 ET (market close)
TS_AFTERHOURS  = 1705357800   # 2024-01-15 16:30 ET


def _snap(
    ts: int,
    o: float = 195.0,
    h: float = 196.5,
    l: float = 194.0,
    c: float = 196.0,
    v: float = 10000.0,
    symbol: str = "GENERIC",
    tf: str = "2",
    date: str = "2024-01-15",
) -> CandleSnapshot:
    return CandleSnapshot(
        timestamp=ts, open=o, high=h, low=l, close=c,
        volume=v, symbol=symbol, timeframe=tf, replay_date=date,
    )


def _rec(snap: CandleSnapshot, idx: int = 0, indicators: dict | None = None) -> CandleRecord:
    return build_record(snap, indicators or {}, idx)


def _write_and_load(tmp_path: Path, records: list[CandleRecord]) -> BacktestReplay:
    path = tmp_path / "day.jsonl"
    with JsonlStore(path) as store:
        for r in records:
            store.append(r)
    return BacktestReplay.from_path(path)


def _extractor(tmp_path: Path, records: list[CandleRecord], config: FeatureConfig | None = None) -> FeatureExtractor:
    replay = _write_and_load(tmp_path, records)
    return FeatureExtractor(replay, config)


# ------------------------------------------------------------------
# FeatureConfig
# ------------------------------------------------------------------

class TestFeatureConfig:
    def test_defaults_are_valid(self):
        cfg = FeatureConfig()
        assert cfg.atr_window == 14
        assert cfg.rvol_window == 20
        assert cfg.max_window >= max(cfg.atr_window, cfg.rvol_window)

    def test_max_window_too_small_raises(self):
        with pytest.raises(ValueError, match="max_window"):
            FeatureConfig(atr_window=20, rvol_window=20, max_window=10)

    def test_atr_window_zero_raises(self):
        with pytest.raises(ValueError, match="atr_window"):
            FeatureConfig(atr_window=0)

    def test_custom_config(self):
        cfg = FeatureConfig(atr_window=5, rvol_window=5, max_window=10)
        assert cfg.atr_window == 5


# ------------------------------------------------------------------
# RollingWindow
# ------------------------------------------------------------------

class TestRollingWindow:
    def test_empty_on_creation(self):
        w = RollingWindow(10)
        assert len(w) == 0
        assert w.is_empty()

    def test_push_and_snapshot(self):
        w = RollingWindow(10)
        r = _rec(_snap(TS_930))
        w.push(r)
        snap = w.snapshot()
        assert len(snap) == 1
        assert snap[0].timestamp == TS_930

    def test_snapshot_is_tuple(self):
        w = RollingWindow(5)
        w.push(_rec(_snap(TS_930)))
        assert isinstance(w.snapshot(), tuple)

    def test_oldest_drops_when_full(self):
        w = RollingWindow(2)
        w.push(_rec(_snap(TS_930)))
        w.push(_rec(_snap(TS_932)))
        w.push(_rec(_snap(TS_934)))
        snap = w.snapshot()
        assert len(snap) == 2
        assert snap[0].timestamp == TS_932  # TS_930 dropped
        assert snap[1].timestamp == TS_934

    def test_last_returns_most_recent(self):
        w = RollingWindow(5)
        w.push(_rec(_snap(TS_930)))
        w.push(_rec(_snap(TS_932)))
        assert w.last().timestamp == TS_932  # type: ignore

    def test_last_on_empty_returns_none(self):
        assert RollingWindow(5).last() is None

    def test_snapshot_ordering_oldest_to_newest(self):
        w = RollingWindow(5)
        for ts in [TS_930, TS_932, TS_934]:
            w.push(_rec(_snap(ts)))
        snap = w.snapshot()
        timestamps = [r.timestamp for r in snap]
        assert timestamps == sorted(timestamps)

    def test_max_size_one(self):
        w = RollingWindow(1)
        w.push(_rec(_snap(TS_930)))
        w.push(_rec(_snap(TS_932)))
        snap = w.snapshot()
        assert len(snap) == 1
        assert snap[0].timestamp == TS_932


# ------------------------------------------------------------------
# Pure feature functions (candle_features.py)
# ------------------------------------------------------------------

class TestCandleBody:
    def test_bullish(self):
        r = _rec(_snap(TS_930, o=194.0, c=196.0))
        assert cf.candle_body(r) == pytest.approx(2.0)

    def test_bearish(self):
        r = _rec(_snap(TS_930, o=196.0, c=194.0))
        assert cf.candle_body(r) == pytest.approx(2.0)

    def test_doji(self):
        r = _rec(_snap(TS_930, o=195.0, c=195.0, h=196.0, l=194.0))
        assert cf.candle_body(r) == pytest.approx(0.0)


class TestWicks:
    def test_upper_wick_bullish(self):
        # open=194, close=196, high=197 → upper_wick = 197 - 196 = 1
        r = _rec(_snap(TS_930, o=194.0, h=197.0, l=193.0, c=196.0))
        assert cf.upper_wick(r) == pytest.approx(1.0)

    def test_lower_wick_bullish(self):
        # open=194, close=196, low=193 → lower_wick = 194 - 193 = 1
        r = _rec(_snap(TS_930, o=194.0, h=197.0, l=193.0, c=196.0))
        assert cf.lower_wick(r) == pytest.approx(1.0)

    def test_upper_wick_bearish(self):
        # open=196, close=194, high=197 → upper_wick = 197 - 196 = 1
        r = _rec(_snap(TS_930, o=196.0, h=197.0, l=193.0, c=194.0))
        assert cf.upper_wick(r) == pytest.approx(1.0)

    def test_lower_wick_bearish(self):
        # open=196, close=194, low=193 → lower_wick = 194 - 193 = 1
        r = _rec(_snap(TS_930, o=196.0, h=197.0, l=193.0, c=194.0))
        assert cf.lower_wick(r) == pytest.approx(1.0)


class TestCandleRange:
    def test_range(self):
        r = _rec(_snap(TS_930, h=200.0, l=195.0))
        assert cf.candle_range(r) == pytest.approx(5.0)

    def test_doji_range_zero(self):
        r = _rec(_snap(TS_930, h=195.0, l=195.0, o=195.0, c=195.0))
        assert cf.candle_range(r) == pytest.approx(0.0)


class TestBodyPct:
    def test_full_body(self):
        # body == range → 100%
        r = _rec(_snap(TS_930, o=194.0, h=196.0, l=194.0, c=196.0))
        assert cf.body_pct(r) == pytest.approx(100.0)

    def test_half_body(self):
        # range=4, body=2 → 50%
        r = _rec(_snap(TS_930, o=195.0, h=197.0, l=193.0, c=197.0))
        assert cf.body_pct(r) == pytest.approx(50.0)

    def test_doji_returns_none(self):
        r = _rec(_snap(TS_930, o=195.0, h=195.0, l=195.0, c=195.0))
        assert cf.body_pct(r) is None


class TestATR:
    def test_empty_window_returns_none(self):
        assert cf.atr((), 14) is None

    def test_single_candle(self):
        w = (_rec(_snap(TS_930, h=196.0, l=194.0)),)  # range=2
        assert cf.atr(w, 14) == pytest.approx(2.0)

    def test_average_of_ranges(self):
        w = (
            _rec(_snap(TS_930, h=196.0, l=194.0)),  # range=2
            _rec(_snap(TS_932, h=197.0, l=193.0)),  # range=4
        )
        assert cf.atr(w, 14) == pytest.approx(3.0)

    def test_window_larger_than_n_uses_last_n(self):
        w = (
            _rec(_snap(TS_930, h=200.0, l=190.0)),  # range=10 — excluded (n=2)
            _rec(_snap(TS_932, h=196.0, l=194.0)),  # range=2
            _rec(_snap(TS_934, h=197.0, l=193.0)),  # range=4
        )
        assert cf.atr(w, 2) == pytest.approx(3.0)


class TestGapAndDistance:
    def test_gap_from_prev_empty_window(self):
        assert cf.gap_from_prev(_rec(_snap(TS_930)), ()) is None

    def test_gap_from_prev(self):
        prev = _rec(_snap(TS_930, c=195.0))
        cur = _rec(_snap(TS_932, o=196.0))
        assert cf.gap_from_prev(cur, (prev,)) == pytest.approx(1.0)

    def test_gap_negative(self):
        prev = _rec(_snap(TS_930, c=197.0))
        cur = _rec(_snap(TS_932, o=195.0))
        assert cf.gap_from_prev(cur, (prev,)) == pytest.approx(-2.0)

    def test_distance_from_prev_close_empty(self):
        assert cf.distance_from_prev_close(_rec(_snap(TS_930)), ()) is None

    def test_distance_from_prev_close(self):
        prev = _rec(_snap(TS_930, c=195.0))
        cur = _rec(_snap(TS_932, c=197.0))
        assert cf.distance_from_prev_close(cur, (prev,)) == pytest.approx(2.0)


class TestStructureFlags:
    def test_hh_true(self):
        prev = _rec(_snap(TS_930, h=196.0))
        cur = _rec(_snap(TS_932, h=197.0))
        assert cf.is_higher_high(cur, (prev,)) is True

    def test_hh_false(self):
        prev = _rec(_snap(TS_930, h=198.0))
        cur = _rec(_snap(TS_932, h=197.0))
        assert cf.is_higher_high(cur, (prev,)) is False

    def test_hh_none_empty_window(self):
        assert cf.is_higher_high(_rec(_snap(TS_930)), ()) is None

    def test_ll_true(self):
        prev = _rec(_snap(TS_930, l=194.0))
        cur = _rec(_snap(TS_932, l=193.0))
        assert cf.is_lower_low(cur, (prev,)) is True

    def test_ll_false(self):
        prev = _rec(_snap(TS_930, l=192.0))
        cur = _rec(_snap(TS_932, l=193.0))
        assert cf.is_lower_low(cur, (prev,)) is False

    def test_inside_bar_true(self):
        prev = _rec(_snap(TS_930, h=200.0, l=190.0))
        cur = _rec(_snap(TS_932, h=198.0, l=192.0))
        assert cf.is_inside_bar(cur, (prev,)) is True

    def test_inside_bar_false(self):
        prev = _rec(_snap(TS_930, h=200.0, l=190.0))
        cur = _rec(_snap(TS_932, h=201.0, l=192.0))
        assert cf.is_inside_bar(cur, (prev,)) is False

    def test_outside_bar_true(self):
        prev = _rec(_snap(TS_930, h=198.0, l=192.0))
        cur = _rec(_snap(TS_932, h=200.0, l=190.0))
        assert cf.is_outside_bar(cur, (prev,)) is True

    def test_outside_bar_false(self):
        prev = _rec(_snap(TS_930, h=200.0, l=190.0))
        cur = _rec(_snap(TS_932, h=198.0, l=192.0))
        assert cf.is_outside_bar(cur, (prev,)) is False


class TestConsecutiveCounts:
    def test_consecutive_hh_empty(self):
        assert cf.consecutive_hh(_rec(_snap(TS_930, h=200.0)), ()) == 0

    def test_consecutive_hh_streak_of_one(self):
        w = (_rec(_snap(TS_930, h=198.0)),)
        cur = _rec(_snap(TS_932, h=200.0))
        assert cf.consecutive_hh(cur, w) == 1

    def test_consecutive_hh_streak_of_three(self):
        w = (
            _rec(_snap(TS_930, h=194.0)),
            _rec(_snap(TS_932, h=196.0)),
            _rec(_snap(TS_934, h=198.0)),
        )
        cur = _rec(_snap(TS_936, h=200.0))
        assert cf.consecutive_hh(cur, w) == 3

    def test_consecutive_hh_broken_streak(self):
        w = (
            _rec(_snap(TS_930, h=200.0)),  # high — breaks streak
            _rec(_snap(TS_932, h=196.0)),
            _rec(_snap(TS_934, h=198.0)),
        )
        cur = _rec(_snap(TS_936, h=200.0))
        # 200 < 200 is False at TS_930, so streak breaks
        assert cf.consecutive_hh(cur, w) == 2

    def test_consecutive_ll_streak(self):
        w = (
            _rec(_snap(TS_930, l=196.0)),
            _rec(_snap(TS_932, l=194.0)),
        )
        cur = _rec(_snap(TS_934, l=192.0))
        assert cf.consecutive_ll(cur, w) == 2

    def test_consecutive_lh_streak(self):
        # lower highs: 200 → 198 → 196 (current)
        w = (
            _rec(_snap(TS_930, h=200.0)),
            _rec(_snap(TS_932, h=198.0)),
        )
        cur = _rec(_snap(TS_934, h=196.0))
        assert cf.consecutive_lh(cur, w) == 2

    def test_consecutive_hl_streak(self):
        # higher lows: 190 → 192 → 194 (current)
        w = (
            _rec(_snap(TS_930, l=190.0)),
            _rec(_snap(TS_932, l=192.0)),
        )
        cur = _rec(_snap(TS_934, l=194.0))
        assert cf.consecutive_hl(cur, w) == 2


class TestRelativeVolume:
    def test_empty_window_returns_none(self):
        cur = _rec(_snap(TS_930, v=10000.0))
        assert cf.relative_volume(cur, (), 20) is None

    def test_rvol_above_average(self):
        # avg volume = 5000, current = 10000 → rvol = 2.0
        w = tuple(_rec(_snap(TS_930 + i * 120, v=5000.0)) for i in range(5))
        cur = _rec(_snap(TS_930 + 600, v=10000.0))
        assert cf.relative_volume(cur, w, 20) == pytest.approx(2.0)

    def test_rvol_uses_available_when_window_smaller_than_n(self):
        w = (_rec(_snap(TS_930, v=5000.0)),)
        cur = _rec(_snap(TS_932, v=10000.0))
        assert cf.relative_volume(cur, w, 20) == pytest.approx(2.0)

    def test_rvol_zero_volume_baseline_returns_none(self):
        w = (_rec(_snap(TS_930, v=0.0)),)
        cur = _rec(_snap(TS_932, v=1000.0))
        assert cf.relative_volume(cur, w, 20) is None


class TestSessionClassification:
    def setup_method(self):
        from src.collector.session_clock import session_end_timestamp
        self.open_ts = session_end_timestamp("2024-01-15", "09:30")
        self.close_ts = session_end_timestamp("2024-01-15", "16:00")

    def test_premarket(self):
        assert cf.classify_session(TS_PREMARKET, self.open_ts, self.close_ts) == "premarket"

    def test_regular_at_open(self):
        assert cf.classify_session(TS_930, self.open_ts, self.close_ts) == "regular"

    def test_regular_mid_day(self):
        assert cf.classify_session(TS_932, self.open_ts, self.close_ts) == "regular"

    def test_after_hours_at_close(self):
        assert cf.classify_session(TS_CLOSE, self.open_ts, self.close_ts) == "after_hours"

    def test_after_hours_past_close(self):
        assert cf.classify_session(TS_AFTERHOURS, self.open_ts, self.close_ts) == "after_hours"


class TestTimeSinceOpen:
    def setup_method(self):
        from src.collector.session_clock import session_end_timestamp
        self.open_ts = session_end_timestamp("2024-01-15", "09:30")

    def test_at_open_zero(self):
        assert cf.time_since_open_minutes(TS_930, self.open_ts) == pytest.approx(0.0)

    def test_two_minutes_after(self):
        assert cf.time_since_open_minutes(TS_932, self.open_ts) == pytest.approx(2.0)

    def test_premarket_negative(self):
        result = cf.time_since_open_minutes(TS_PREMARKET, self.open_ts)
        assert result < 0


class TestDistanceFromSessionOpen:
    def test_none_before_first_regular_candle(self):
        cur = _rec(_snap(TS_PREMARKET, c=194.0))
        assert cf.distance_from_session_open(cur, None) is None

    def test_zero_at_session_open_candle(self):
        # session_open_price == first regular candle close
        cur = _rec(_snap(TS_930, c=195.0))
        assert cf.distance_from_session_open(cur, 195.0) == pytest.approx(0.0)

    def test_positive_when_above_open(self):
        cur = _rec(_snap(TS_932, c=197.0))
        assert cf.distance_from_session_open(cur, 195.0) == pytest.approx(2.0)


# ------------------------------------------------------------------
# FeatureRecord
# ------------------------------------------------------------------

class TestFeatureRecord:
    def _make_record(self, **overrides) -> FeatureRecord:
        base = dict(
            timestamp=TS_930, symbol="GENERIC", timeframe="2",
            replay_date="2024-01-15", candle_index=0,
            open=195.0, high=196.5, low=194.0, close=196.0, volume=10000.0,
            candle_body=1.0, upper_wick=0.5, lower_wick=0.0, body_pct=50.0,
            candle_range=2.5, atr=None, gap_from_prev=None,
            distance_from_prev_close=None, is_higher_high=None, is_lower_low=None,
            is_inside_bar=None, is_outside_bar=None,
            consecutive_hh=0, consecutive_ll=0, consecutive_lh=0, consecutive_hl=0,
            relative_volume=None, session="regular", time_since_open_minutes=0.0,
            distance_from_session_open=0.0, indicators={"RSI": 55.0},
        )
        base.update(overrides)
        return FeatureRecord(**base)

    def test_to_dict_has_all_fields(self):
        r = self._make_record()
        d = r.to_dict()
        for field in ("timestamp", "symbol", "session", "candle_body",
                      "consecutive_hh", "indicators"):
            assert field in d

    def test_to_jsonl_line_is_compact(self):
        r = self._make_record()
        line = r.to_jsonl_line()
        assert "\n" not in line
        parsed = json.loads(line)
        assert parsed["symbol"] == "GENERIC"

    def test_roundtrip_from_dict(self):
        r = self._make_record(atr=1.5, relative_volume=2.0)
        r2 = FeatureRecord.from_dict(r.to_dict())
        assert r2.timestamp == r.timestamp
        assert r2.atr == r.atr
        assert r2.relative_volume == r.relative_volume
        assert r2.indicators == r.indicators

    def test_validate_valid_record(self):
        r = self._make_record()
        assert r.validate() == []

    def test_validate_invalid_session(self):
        r = self._make_record(session="lunch")
        errors = r.validate()
        assert any("session" in e for e in errors)

    def test_validate_negative_body(self):
        r = self._make_record(candle_body=-1.0)
        errors = r.validate()
        assert any("candle_body" in e for e in errors)

    def test_validate_high_less_than_low(self):
        r = self._make_record(high=190.0, low=195.0)
        errors = r.validate()
        assert any("high" in e for e in errors)

    def test_nullable_fields_serialise_as_null(self):
        r = self._make_record(atr=None, gap_from_prev=None)
        d = r.to_dict()
        assert d["atr"] is None
        assert d["gap_from_prev"] is None


# ------------------------------------------------------------------
# FeatureExtractor: integration tests
# ------------------------------------------------------------------

class TestFeatureExtractorSetup:
    def test_requires_backtest_replay(self, tmp_path):
        from src.engine.replay_engine import ReplayEngine
        path = tmp_path / "day.jsonl"
        records = [_rec(_snap(TS_930, date="2024-01-15"), i) for i in range(1)]
        with JsonlStore(path) as store:
            for r in records:
                store.append(r)
        engine = ReplayEngine(path)
        with pytest.raises(TypeError, match="BacktestReplay"):
            FeatureExtractor(engine)  # type: ignore

    def test_accepts_backtest_replay(self, tmp_path):
        records = [_rec(_snap(TS_930), 0)]
        ext = _extractor(tmp_path, records)
        assert ext is not None


class TestOneRecordPerCandle:
    def test_n_candles_produce_n_records(self, tmp_path):
        candles = [_rec(_snap(TS_930 + i * 120), i) for i in range(5)]
        ext = _extractor(tmp_path, candles)
        records = ext.run()
        assert len(records) == 5

    def test_single_candle_produces_one_record(self, tmp_path):
        ext = _extractor(tmp_path, [_rec(_snap(TS_930), 0)])
        records = ext.run()
        assert len(records) == 1

    def test_candle_indices_are_sequential(self, tmp_path):
        candles = [_rec(_snap(TS_930 + i * 120), i) for i in range(4)]
        ext = _extractor(tmp_path, candles)
        records = ext.run()
        assert [r.candle_index for r in records] == [0, 1, 2, 3]


class TestNoLookahead:
    def test_first_candle_has_no_history_features(self, tmp_path):
        ext = _extractor(tmp_path, [_rec(_snap(TS_930), 0)])
        records = ext.run()
        r = records[0]
        # All features requiring previous candle must be None
        assert r.atr is None
        assert r.gap_from_prev is None
        assert r.distance_from_prev_close is None
        assert r.is_higher_high is None
        assert r.is_lower_low is None
        assert r.is_inside_bar is None
        assert r.is_outside_bar is None
        assert r.relative_volume is None
        assert r.consecutive_hh == 0
        assert r.consecutive_ll == 0

    def test_second_candle_uses_only_first_as_history(self, tmp_path):
        candles = [
            _rec(_snap(TS_930, h=196.0, l=194.0, c=195.0), 0),
            _rec(_snap(TS_932, h=197.0, l=195.0, c=196.0), 1),
        ]
        ext = _extractor(tmp_path, candles)
        records = ext.run()
        r1 = records[1]
        # is_higher_high should compare TS_932 to TS_930 only
        assert r1.is_higher_high is True  # 197 > 196
        assert r1.atr is not None         # 1 candle of history is enough for ATR


class TestDeterminism:
    def test_same_input_same_output(self, tmp_path):
        candles = [
            _rec(_snap(TS_930 + i * 120, h=196.0 + i * 0.5, l=194.0, c=195.0 + i * 0.3), i)
            for i in range(5)
        ]
        ext1 = _extractor(tmp_path, candles)
        records1 = ext1.run()

        ext2 = _extractor(tmp_path, candles)
        records2 = ext2.run()

        for r1, r2 in zip(records1, records2):
            assert r1.to_dict() == r2.to_dict()


class TestPriceActionFeatures:
    def test_candle_body_calculation(self, tmp_path):
        # o=194, c=196 → body = 2.0
        ext = _extractor(tmp_path, [_rec(_snap(TS_930, o=194.0, c=196.0), 0)])
        r = ext.run()[0]
        assert r.candle_body == pytest.approx(2.0)

    def test_upper_wick_calculation(self, tmp_path):
        # o=194, h=198, l=193, c=196 → upper_wick = 198 - 196 = 2
        ext = _extractor(tmp_path, [_rec(_snap(TS_930, o=194.0, h=198.0, l=193.0, c=196.0), 0)])
        r = ext.run()[0]
        assert r.upper_wick == pytest.approx(2.0)

    def test_lower_wick_calculation(self, tmp_path):
        # o=194, h=198, l=193, c=196 → lower_wick = 194 - 193 = 1
        ext = _extractor(tmp_path, [_rec(_snap(TS_930, o=194.0, h=198.0, l=193.0, c=196.0), 0)])
        r = ext.run()[0]
        assert r.lower_wick == pytest.approx(1.0)

    def test_range_calculation(self, tmp_path):
        ext = _extractor(tmp_path, [_rec(_snap(TS_930, h=200.0, l=195.0), 0)])
        r = ext.run()[0]
        assert r.candle_range == pytest.approx(5.0)

    def test_body_pct_doji_is_none(self, tmp_path):
        ext = _extractor(tmp_path, [_rec(_snap(TS_930, o=195.0, h=195.0, l=195.0, c=195.0), 0)])
        r = ext.run()[0]
        assert r.body_pct is None


class TestStructureFeatures:
    def _two_candle_extractor(self, tmp_path, snap1, snap2):
        return _extractor(tmp_path, [_rec(snap1, 0), _rec(snap2, 1)])

    def test_inside_bar_detected(self, tmp_path):
        ext = self._two_candle_extractor(
            tmp_path,
            _snap(TS_930, h=200.0, l=190.0),
            _snap(TS_932, h=198.0, l=192.0),
        )
        records = ext.run()
        assert records[1].is_inside_bar is True

    def test_outside_bar_detected(self, tmp_path):
        ext = self._two_candle_extractor(
            tmp_path,
            _snap(TS_930, h=198.0, l=192.0),
            _snap(TS_932, h=200.0, l=190.0),
        )
        records = ext.run()
        assert records[1].is_outside_bar is True

    def test_consecutive_hh_grows_with_streak(self, tmp_path):
        candles = [
            _rec(_snap(TS_930 + i * 120, h=194.0 + i), i)
            for i in range(4)
        ]
        ext = _extractor(tmp_path, candles)
        records = ext.run()
        assert records[0].consecutive_hh == 0  # no history
        assert records[1].consecutive_hh == 1  # one HH
        assert records[2].consecutive_hh == 2  # two HH streak
        assert records[3].consecutive_hh == 3  # three HH streak

    def test_consecutive_hh_resets_on_lower_high(self, tmp_path):
        candles = [
            _rec(_snap(TS_930, h=200.0), 0),
            _rec(_snap(TS_932, h=198.0), 1),  # lower high — breaks HH streak
            _rec(_snap(TS_934, h=202.0), 2),  # new HH (only 1 streak from 198)
        ]
        ext = _extractor(tmp_path, candles)
        records = ext.run()
        assert records[2].consecutive_hh == 1


class TestVolumeFeatures:
    def test_relative_volume_none_for_first_candle(self, tmp_path):
        ext = _extractor(tmp_path, [_rec(_snap(TS_930, v=10000.0), 0)])
        r = ext.run()[0]
        assert r.relative_volume is None

    def test_relative_volume_calculated(self, tmp_path):
        # 3 candles: first two with v=5000, third with v=10000 → rvol=2.0
        config = FeatureConfig(atr_window=2, rvol_window=2, max_window=10)
        candles = [
            _rec(_snap(TS_930, v=5000.0), 0),
            _rec(_snap(TS_932, v=5000.0), 1),
            _rec(_snap(TS_934, v=10000.0), 2),
        ]
        ext = _extractor(tmp_path, candles, config)
        records = ext.run()
        assert records[2].relative_volume == pytest.approx(2.0)


class TestSessionFeatures:
    def test_premarket_candle_labelled(self, tmp_path):
        ext = _extractor(tmp_path, [_rec(_snap(TS_PREMARKET, date="2024-01-15"), 0)])
        r = ext.run()[0]
        assert r.session == "premarket"

    def test_regular_candle_labelled(self, tmp_path):
        ext = _extractor(tmp_path, [_rec(_snap(TS_930), 0)])
        r = ext.run()[0]
        assert r.session == "regular"

    def test_after_hours_candle_labelled(self, tmp_path):
        ext = _extractor(tmp_path, [_rec(_snap(TS_AFTERHOURS), 0)])
        r = ext.run()[0]
        assert r.session == "after_hours"

    def test_time_since_open_at_930(self, tmp_path):
        ext = _extractor(tmp_path, [_rec(_snap(TS_930), 0)])
        r = ext.run()[0]
        assert r.time_since_open_minutes == pytest.approx(0.0)

    def test_time_since_open_two_minutes(self, tmp_path):
        ext = _extractor(tmp_path, [_rec(_snap(TS_932), 0)])
        r = ext.run()[0]
        assert r.time_since_open_minutes == pytest.approx(2.0)

    def test_premarket_negative_time_since_open(self, tmp_path):
        ext = _extractor(tmp_path, [_rec(_snap(TS_PREMARKET, date="2024-01-15"), 0)])
        r = ext.run()[0]
        assert r.time_since_open_minutes < 0

    def test_distance_from_session_open_none_for_premarket(self, tmp_path):
        # Only premarket candle — session_open_price never set
        ext = _extractor(tmp_path, [_rec(_snap(TS_PREMARKET, date="2024-01-15"), 0)])
        r = ext.run()[0]
        assert r.distance_from_session_open is None

    def test_distance_from_session_open_zero_at_open(self, tmp_path):
        ext = _extractor(tmp_path, [_rec(_snap(TS_930, c=195.0), 0)])
        r = ext.run()[0]
        # First regular candle: distance = close - close = 0
        assert r.distance_from_session_open == pytest.approx(0.0)

    def test_distance_from_session_open_tracks_move(self, tmp_path):
        candles = [
            _rec(_snap(TS_930, c=195.0), 0),
            _rec(_snap(TS_932, c=197.0), 1),
        ]
        ext = _extractor(tmp_path, candles)
        records = ext.run()
        assert records[1].distance_from_session_open == pytest.approx(2.0)


class TestIndicatorPassthrough:
    def test_indicators_passed_through(self, tmp_path):
        snap = _snap(TS_930)
        rec = build_record(snap, {"RSI": 55.2, "VWAP": 195.5}, 0)
        replay = _write_and_load(tmp_path, [rec])
        ext = FeatureExtractor(replay)
        records = ext.run()
        assert records[0].indicators == {"RSI": 55.2, "VWAP": 195.5}

    def test_empty_indicators_produces_empty_dict(self, tmp_path):
        ext = _extractor(tmp_path, [_rec(_snap(TS_930), 0)])
        r = ext.run()[0]
        assert r.indicators == {}

    def test_indicators_not_modified(self, tmp_path):
        snap = _snap(TS_930)
        rec = build_record(snap, {"RSI": 42.0}, 0)
        replay = _write_and_load(tmp_path, [rec])
        ext = FeatureExtractor(replay)
        records = ext.run()
        assert records[0].indicators["RSI"] == 42.0


class TestSchemaValidation:
    def test_all_records_valid(self, tmp_path):
        candles = [
            _rec(_snap(TS_PREMARKET, date="2024-01-15"), 0),
            _rec(_snap(TS_930), 1),
            _rec(_snap(TS_932), 2),
            _rec(_snap(TS_AFTERHOURS), 3),
        ]
        ext = _extractor(tmp_path, candles)
        records = ext.run()
        for i, r in enumerate(records):
            errors = r.validate()
            assert errors == [], f"Record {i} has validation errors: {errors}"


class TestATRInExtractor:
    def test_atr_available_after_first_candle(self, tmp_path):
        candles = [
            _rec(_snap(TS_930, h=196.0, l=194.0), 0),  # range=2
            _rec(_snap(TS_932, h=197.0, l=195.0), 1),
        ]
        ext = _extractor(tmp_path, candles)
        records = ext.run()
        assert records[0].atr is None   # no history
        assert records[1].atr == pytest.approx(2.0)  # avg of [range(TS_930)]

    def test_atr_averages_over_window(self, tmp_path):
        config = FeatureConfig(atr_window=2, rvol_window=2, max_window=10)
        candles = [
            _rec(_snap(TS_930 + i * 120, h=196.0 + i, l=194.0), i)
            for i in range(3)
        ]
        ext = _extractor(tmp_path, candles, config)
        records = ext.run()
        # Record at index 2 has window = [candle0, candle1]
        # ranges: candle0 h=196 l=194 → 2; candle1 h=197 l=194 → 3; avg = 2.5
        assert records[2].atr == pytest.approx(2.5)


class TestStepAPI:
    def test_step_returns_feature_record(self, tmp_path):
        ext = _extractor(tmp_path, [_rec(_snap(TS_930), 0)])
        r = ext.step()
        assert isinstance(r, FeatureRecord)

    def test_step_advances_candle_index(self, tmp_path):
        candles = [_rec(_snap(TS_930 + i * 120), i) for i in range(3)]
        ext = _extractor(tmp_path, candles)
        r0 = ext.step()
        r1 = ext.step()
        r2 = ext.step()
        assert r0.candle_index == 0
        assert r1.candle_index == 1
        assert r2.candle_index == 2

    def test_step_at_last_candle_does_not_raise(self, tmp_path):
        ext = _extractor(tmp_path, [_rec(_snap(TS_930), 0)])
        r = ext.step()  # last candle — should not raise
        assert r.candle_index == 0


class TestNoBizLogic:
    def test_no_trading_terms_in_extractor(self):
        import inspect
        from src.features import extractor as mod
        source = inspect.getsource(mod)
        forbidden = ["buy", "sell", "entry", "exit", "stop_loss",
                     "take_profit", "ltp", "rejection", "reversal", "bounce",
                     "heatseeker"]
        for term in forbidden:
            assert term not in source.lower(), (
                f"Trading term {term!r} found in extractor.py"
            )

    def test_no_hardcoded_ticker_in_extractor(self):
        import inspect
        from src.features import extractor as mod
        source = inspect.getsource(mod)
        for ticker in ("TSLA", "AAPL", "SPY"):
            assert ticker not in source, f"Ticker {ticker!r} hardcoded in extractor.py"

    def test_extractor_does_not_import_replay_engine(self):
        import ast
        from pathlib import Path
        import src.features.extractor as mod
        src_path = Path(mod.__file__)
        tree = ast.parse(src_path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = getattr(node, "module", "") or ""
                names = [a.name for a in getattr(node, "names", [])]
                for ref in [module] + names:
                    assert "replay_engine" not in ref.lower(), (
                        f"extractor.py must not import from replay_engine, found: {ref}"
                    )
