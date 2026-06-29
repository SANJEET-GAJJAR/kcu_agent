"""Unit tests for ReplayEngine. No TradingView dependency."""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from datetime import timezone

from src.collector.candle_schema import CandleSnapshot
from src.collector.candle_record import CandleRecord, build_record
from src.collector.jsonl_store import JsonlStore
from src.engine.replay_engine import (
    ReplayEngine,
    ReplayEngineError,
    BeginningOfReplay,
    EndOfReplay,
    TimestampNotFound,
    ReplayState,
    _parse_timestamp,
)


# ------------------------------------------------------------------
# Fixture helpers
# ------------------------------------------------------------------

def _snap(ts: int, symbol: str = "TSLA", tf: str = "2") -> CandleSnapshot:
    return CandleSnapshot(
        timestamp=ts, open=195.0, high=196.5, low=194.0, close=196.0,
        volume=float(ts % 10000 + 1000),  # vary volume so records are distinguishable
        symbol=symbol, timeframe=tf, replay_date="2024-01-15",
    )


def _write_jsonl(path: Path, timestamps: list[int], symbol: str = "TSLA", tf: str = "2") -> Path:
    """Write a JSONL file with candles at the given timestamps."""
    with JsonlStore(path) as store:
        for i, ts in enumerate(timestamps):
            store.append(build_record(_snap(ts, symbol, tf), {"RSI": 50.0 + i}, i))
    return path


def _engine(tmp_path: Path, timestamps: list[int], **kw) -> ReplayEngine:
    path = tmp_path / "day.jsonl"
    _write_jsonl(path, timestamps, **kw)
    return ReplayEngine(path)


# Representative timestamps: 09:30, 09:32, 09:34 ET on 2024-01-15
# 2024-01-15 is EST (UTC-5)
# 09:30 EST = 14:30 UTC = 1705329000
TS_930  = 1705329000
TS_932  = 1705329120
TS_934  = 1705329240
TS_936  = 1705329360
TS_938  = 1705329480


# ------------------------------------------------------------------
# Loading
# ------------------------------------------------------------------

class TestLoading:
    def test_loads_valid_jsonl(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932, TS_934])
        assert engine.total_candles == 3

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(ReplayEngineError, match="not found"):
            ReplayEngine(tmp_path / "missing.jsonl")

    def test_empty_file_raises(self, tmp_path):
        path = tmp_path / "empty.jsonl"
        path.touch()
        with pytest.raises(ReplayEngineError, match="empty"):
            ReplayEngine(path)

    def test_corrupt_file_raises(self, tmp_path):
        path = tmp_path / "corrupt.jsonl"
        path.write_text("not json\n")
        with pytest.raises(ReplayEngineError):
            ReplayEngine(path)

    def test_out_of_order_jsonl_sorted_on_load(self, tmp_path):
        # Write out of order — engine must sort
        path = tmp_path / "unsorted.jsonl"
        with JsonlStore(path) as store:
            store.append(build_record(_snap(TS_934), {}, 0))
            store.append(build_record(_snap(TS_930), {}, 1))
            store.append(build_record(_snap(TS_932), {}, 2))
        # Bypass duplicate check by writing raw lines for the already-seen ts
        engine = ReplayEngine(path)
        timestamps = [engine.current().timestamp]
        engine.next(); timestamps.append(engine.current().timestamp)
        engine.next(); timestamps.append(engine.current().timestamp)
        assert timestamps == sorted(timestamps)

    def test_duplicate_timestamps_deduped_on_load(self, tmp_path):
        path = tmp_path / "dup.jsonl"
        rec = build_record(_snap(TS_930), {}, 0)
        # Write same timestamp twice manually
        with path.open("w") as f:
            f.write(rec.to_jsonl_line() + "\n")
            f.write(rec.to_jsonl_line() + "\n")
        engine = ReplayEngine(path)
        assert engine.total_candles == 1

    def test_starts_at_first_candle(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932, TS_934])
        assert engine.current().timestamp == TS_930
        assert engine.cursor == 0


# ------------------------------------------------------------------
# current()
# ------------------------------------------------------------------

class TestCurrent:
    def test_current_returns_candle_record(self, tmp_path):
        engine = _engine(tmp_path, [TS_930])
        assert isinstance(engine.current(), CandleRecord)

    def test_current_does_not_advance(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932])
        _ = engine.current()
        _ = engine.current()
        assert engine.cursor == 0

    def test_current_returns_correct_candle_after_advance(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932, TS_934])
        engine.next()
        assert engine.current().timestamp == TS_932


# ------------------------------------------------------------------
# next()
# ------------------------------------------------------------------

class TestNext:
    def test_next_advances_cursor(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932, TS_934])
        engine.next()
        assert engine.cursor == 1

    def test_next_returns_new_current(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932])
        candle = engine.next()
        assert candle.timestamp == TS_932

    def test_next_at_last_candle_raises(self, tmp_path):
        engine = _engine(tmp_path, [TS_930])
        with pytest.raises(EndOfReplay):
            engine.next()

    def test_next_traverses_all_candles(self, tmp_path):
        timestamps = [TS_930, TS_932, TS_934, TS_936, TS_938]
        engine = _engine(tmp_path, timestamps)
        seen = [engine.current().timestamp]
        for _ in range(len(timestamps) - 1):
            seen.append(engine.next().timestamp)
        assert seen == timestamps

    def test_next_at_second_to_last_reaches_last(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932])
        engine.next()
        assert engine.finished()


# ------------------------------------------------------------------
# previous()
# ------------------------------------------------------------------

class TestPrevious:
    def test_previous_moves_back(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932, TS_934])
        engine.next()
        engine.next()
        engine.previous()
        assert engine.cursor == 1
        assert engine.current().timestamp == TS_932

    def test_previous_at_start_raises(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932])
        with pytest.raises(BeginningOfReplay):
            engine.previous()

    def test_next_then_previous_returns_to_start(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932])
        engine.next()
        engine.previous()
        assert engine.cursor == 0
        assert engine.current().timestamp == TS_930

    def test_previous_returns_new_current(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932])
        engine.next()
        candle = engine.previous()
        assert candle.timestamp == TS_930


# ------------------------------------------------------------------
# goto()
# ------------------------------------------------------------------

class TestGoto:
    def test_goto_int_timestamp(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932, TS_934])
        candle = engine.goto(TS_934)
        assert candle.timestamp == TS_934
        assert engine.cursor == 2

    def test_goto_iso_string_with_timezone(self, tmp_path):
        # TS_930 = 2024-01-15 14:30:00 UTC = 09:30:00 EST
        engine = _engine(tmp_path, [TS_930, TS_932])
        candle = engine.goto("2024-01-15T14:30:00+00:00")
        assert candle.timestamp == TS_930

    def test_goto_iso_string_utc_z(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932])
        candle = engine.goto("2024-01-15T14:30:00Z")
        assert candle.timestamp == TS_930

    def test_goto_iso_string_et_offset(self, tmp_path):
        # 09:30 EST = UTC-5 → 14:30 UTC
        engine = _engine(tmp_path, [TS_930, TS_932])
        candle = engine.goto("2024-01-15T09:30:00-05:00")
        assert candle.timestamp == TS_930

    def test_goto_integer_string(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932, TS_934])
        candle = engine.goto(str(TS_932))
        assert candle.timestamp == TS_932

    def test_goto_unknown_timestamp_raises(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932])
        with pytest.raises(TimestampNotFound):
            engine.goto(9999999999)

    def test_goto_can_move_backward(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932, TS_934])
        engine.next()
        engine.next()
        engine.goto(TS_930)
        assert engine.cursor == 0

    def test_goto_middle_candle(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932, TS_934, TS_936])
        engine.goto(TS_934)
        assert engine.cursor == 2


# ------------------------------------------------------------------
# finished() / at_beginning()
# ------------------------------------------------------------------

class TestBoundaryDetection:
    def test_finished_false_at_start(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932])
        assert engine.finished() is False

    def test_finished_true_at_last(self, tmp_path):
        engine = _engine(tmp_path, [TS_930])
        assert engine.finished() is True

    def test_finished_true_after_reaching_last(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932])
        engine.next()
        assert engine.finished() is True

    def test_at_beginning_true_initially(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932])
        assert engine.at_beginning() is True

    def test_at_beginning_false_after_next(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932])
        engine.next()
        assert engine.at_beginning() is False

    def test_at_beginning_true_after_reset(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932])
        engine.next()
        engine.reset()
        assert engine.at_beginning() is True

    def test_single_candle_both_flags(self, tmp_path):
        engine = _engine(tmp_path, [TS_930])
        assert engine.at_beginning() is True
        assert engine.finished() is True


# ------------------------------------------------------------------
# reset()
# ------------------------------------------------------------------

class TestReset:
    def test_reset_returns_to_start(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932, TS_934])
        engine.next()
        engine.next()
        engine.reset()
        assert engine.cursor == 0
        assert engine.current().timestamp == TS_930


# ------------------------------------------------------------------
# state()
# ------------------------------------------------------------------

class TestReplayState:
    def test_state_fields(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932])
        s = engine.state()
        assert isinstance(s, ReplayState)
        assert s.cursor == 0
        assert s.total_candles == 2
        assert s.current_timestamp == TS_930
        assert s.symbol == "TSLA"
        assert s.timeframe == "2"

    def test_state_is_frozen(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932])
        s = engine.state()
        with pytest.raises((AttributeError, TypeError)):
            s.cursor = 99  # type: ignore

    def test_state_to_dict(self, tmp_path):
        engine = _engine(tmp_path, [TS_930])
        d = engine.state().to_dict()
        assert "cursor" in d
        assert "total_candles" in d
        assert "current_timestamp" in d

    def test_state_updates_after_next(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932])
        engine.next()
        s = engine.state()
        assert s.cursor == 1
        assert s.current_timestamp == TS_932


# ------------------------------------------------------------------
# Determinism
# ------------------------------------------------------------------

class TestDeterminism:
    def test_same_file_same_order(self, tmp_path):
        timestamps = [TS_930, TS_932, TS_934, TS_936, TS_938]
        path = tmp_path / "day.jsonl"
        _write_jsonl(path, timestamps)

        def collect_all(p):
            eng = ReplayEngine(p)
            result = [eng.current().timestamp]
            while not eng.finished():
                result.append(eng.next().timestamp)
            return result

        assert collect_all(path) == collect_all(path)

    def test_replay_order_equals_sorted_timestamps(self, tmp_path):
        timestamps = [TS_930, TS_932, TS_934, TS_936]
        engine = _engine(tmp_path, timestamps)
        seen = [engine.current().timestamp]
        while not engine.finished():
            seen.append(engine.next().timestamp)
        assert seen == sorted(timestamps)


# ------------------------------------------------------------------
# No lookahead
# ------------------------------------------------------------------

class TestNoLookahead:
    def test_cursor_never_exposes_future(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932, TS_934])
        # At cursor=0, only candle at TS_930 should be "current"
        assert engine.current().timestamp == TS_930
        # Accessing candles by index must go through the engine API
        # (the internal _candles tuple is accessible in Python but that's
        # an implementation detail — the public API is safe)

    def test_peek_next_is_only_allowed_internal_lookahead(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932, TS_934])
        # peek_next is documented as engine-internal; it must exist and work
        peeked = engine.peek_next()
        assert peeked is not None
        assert peeked.timestamp == TS_932
        # Peeking does NOT advance cursor
        assert engine.cursor == 0
        assert engine.current().timestamp == TS_930

    def test_peek_next_at_end_returns_none(self, tmp_path):
        engine = _engine(tmp_path, [TS_930])
        assert engine.peek_next() is None


# ------------------------------------------------------------------
# Properties
# ------------------------------------------------------------------

class TestProperties:
    def test_symbol_property(self, tmp_path):
        engine = _engine(tmp_path, [TS_930], symbol="AAPL")
        assert engine.symbol == "AAPL"

    def test_timeframe_property(self, tmp_path):
        engine = _engine(tmp_path, [TS_930], tf="5")
        assert engine.timeframe == "5"

    def test_total_candles_property(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932, TS_934])
        assert engine.total_candles == 3

    def test_len(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932])
        assert len(engine) == 2

    def test_repr_contains_filename(self, tmp_path):
        engine = _engine(tmp_path, [TS_930])
        assert "day.jsonl" in repr(engine)

    def test_source_path_property(self, tmp_path):
        path = tmp_path / "day.jsonl"
        _write_jsonl(path, [TS_930])
        engine = ReplayEngine(path)
        assert engine.source_path == path


# ------------------------------------------------------------------
# Iteration
# ------------------------------------------------------------------

class TestIteration:
    def test_iteration_yields_all_candles_including_last(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932, TS_934])
        seen = [c.timestamp for c in engine]
        assert seen == [TS_930, TS_932, TS_934]

    def test_iteration_does_not_reset(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932, TS_934])
        engine.next()  # Start from second candle
        seen = [c.timestamp for c in engine]
        assert seen == [TS_932, TS_934]
        assert TS_930 not in seen  # Already past it

    def test_iteration_single_candle(self, tmp_path):
        engine = _engine(tmp_path, [TS_930])
        seen = [c.timestamp for c in engine]
        assert seen == [TS_930]

    def test_iteration_leaves_cursor_at_last(self, tmp_path):
        engine = _engine(tmp_path, [TS_930, TS_932, TS_934])
        list(engine)  # exhaust
        assert engine.finished()
        assert engine.current().timestamp == TS_934

    def test_second_iteration_restarts_from_cursor(self, tmp_path):
        # __iter__ resets _iter_done so a second for-loop works from current cursor
        engine = _engine(tmp_path, [TS_930, TS_932, TS_934])
        list(engine)  # exhaust — cursor now at last
        seen = [c.timestamp for c in engine]
        assert seen == [TS_934]  # cursor stayed at last, so only one candle


# ------------------------------------------------------------------
# _parse_timestamp helper
# ------------------------------------------------------------------

class TestParseTimestamp:
    def test_int_passthrough(self):
        assert _parse_timestamp(1705329000) == 1705329000

    def test_float_truncated(self):
        assert _parse_timestamp(1705329000.9) == 1705329000

    def test_iso_utc(self):
        ts = _parse_timestamp("2024-01-15T14:30:00Z")
        assert ts == 1705329000

    def test_iso_offset(self):
        ts = _parse_timestamp("2024-01-15T09:30:00-05:00")
        assert ts == 1705329000

    def test_string_int(self):
        assert _parse_timestamp("1705329000") == 1705329000

    def test_invalid_string_raises(self):
        with pytest.raises(TimestampNotFound):
            _parse_timestamp("not-a-date")

    def test_unsupported_type_raises(self):
        with pytest.raises(TimestampNotFound):
            _parse_timestamp([1, 2, 3])  # type: ignore


# ------------------------------------------------------------------
# Generic (ticker-agnostic)
# ------------------------------------------------------------------

class TestGeneric:
    def test_works_with_any_symbol(self, tmp_path):
        for symbol in ("AAPL", "SPY", "QQQ", "ES1!", "NVDA"):
            engine = _engine(tmp_path / f"{symbol}.jsonl", [TS_930, TS_932], symbol=symbol)
            # Need to write file first
            path = tmp_path / f"{symbol}_day.jsonl"
            _write_jsonl(path, [TS_930, TS_932], symbol=symbol)
            eng = ReplayEngine(path)
            assert eng.symbol == symbol

    def test_no_hardcoded_ticker_in_source(self):
        import inspect
        from src.engine import replay_engine as mod
        source = inspect.getsource(mod)
        for ticker in ("TSLA", "AAPL", "SPY"):
            assert ticker not in source, f"Ticker {ticker!r} hardcoded in replay_engine.py"

    def test_no_trading_logic_in_source(self):
        import inspect
        from src.engine import replay_engine as mod
        source = inspect.getsource(mod)
        forbidden = ["buy", "sell", "entry", "exit", "stop_loss",
                     "take_profit", "ltp", "rejection", "reversal", "bounce"]
        for term in forbidden:
            assert term not in source, f"Trading term {term!r} in replay_engine.py"
