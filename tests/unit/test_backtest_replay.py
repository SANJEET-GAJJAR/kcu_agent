"""Unit tests for BacktestReplay forward-only guard."""
from __future__ import annotations

import pytest
from pathlib import Path

from src.collector.candle_schema import CandleSnapshot
from src.collector.candle_record import CandleRecord, build_record
from src.collector.jsonl_store import JsonlStore
from src.engine.replay_engine import ReplayEngine, EndOfReplay
from src.engine.backtest_replay import BacktestReplay, LookaheadGuardError

# Representative timestamps: 09:30–09:38 ET on 2024-01-15 (EST = UTC-5)
TS_930 = 1705329000
TS_932 = 1705329120
TS_934 = 1705329240
TS_936 = 1705329360


def _snap(ts: int) -> CandleSnapshot:
    return CandleSnapshot(
        timestamp=ts, open=195.0, high=196.5, low=194.0, close=196.0,
        volume=10000.0, symbol="GENERIC", timeframe="2", replay_date="2024-01-15",
    )


def _write_jsonl(path: Path, timestamps: list[int]) -> Path:
    with JsonlStore(path) as store:
        for i, ts in enumerate(timestamps):
            store.append(build_record(_snap(ts), {}, i))
    return path


def _replay(tmp_path: Path, timestamps: list[int]) -> BacktestReplay:
    path = tmp_path / "day.jsonl"
    _write_jsonl(path, timestamps)
    return BacktestReplay.from_path(path)


# ------------------------------------------------------------------
# Permitted operations
# ------------------------------------------------------------------

class TestPermittedOperations:
    def test_current_returns_first_candle(self, tmp_path):
        r = _replay(tmp_path, [TS_930, TS_932])
        assert r.current().timestamp == TS_930

    def test_next_advances(self, tmp_path):
        r = _replay(tmp_path, [TS_930, TS_932])
        candle = r.next()
        assert candle.timestamp == TS_932
        assert r.cursor == 1

    def test_next_at_last_raises_end_of_replay(self, tmp_path):
        r = _replay(tmp_path, [TS_930])
        with pytest.raises(EndOfReplay):
            r.next()

    def test_goto_forward_permitted(self, tmp_path):
        r = _replay(tmp_path, [TS_930, TS_932, TS_934])
        candle = r.goto(TS_934)
        assert candle.timestamp == TS_934

    def test_goto_same_timestamp_permitted(self, tmp_path):
        # Jumping to current position is a no-op, not backward
        r = _replay(tmp_path, [TS_930, TS_932])
        candle = r.goto(TS_930)
        assert candle.timestamp == TS_930

    def test_finished_false_at_start(self, tmp_path):
        r = _replay(tmp_path, [TS_930, TS_932])
        assert r.finished() is False

    def test_finished_true_at_last(self, tmp_path):
        r = _replay(tmp_path, [TS_930])
        assert r.finished() is True

    def test_at_beginning_true_initially(self, tmp_path):
        r = _replay(tmp_path, [TS_930, TS_932])
        assert r.at_beginning() is True

    def test_at_beginning_false_after_next(self, tmp_path):
        r = _replay(tmp_path, [TS_930, TS_932])
        r.next()
        assert r.at_beginning() is False

    def test_state_returns_replay_state(self, tmp_path):
        r = _replay(tmp_path, [TS_930, TS_932])
        s = r.state()
        assert s.cursor == 0
        assert s.current_timestamp == TS_930
        assert s.symbol == "GENERIC"


# ------------------------------------------------------------------
# Blocked operations
# ------------------------------------------------------------------

class TestBlockedOperations:
    def test_previous_raises(self, tmp_path):
        r = _replay(tmp_path, [TS_930, TS_932])
        r.next()
        with pytest.raises(LookaheadGuardError, match="previous"):
            r.previous()

    def test_previous_raises_even_at_start(self, tmp_path):
        r = _replay(tmp_path, [TS_930])
        with pytest.raises(LookaheadGuardError):
            r.previous()

    def test_reset_raises(self, tmp_path):
        r = _replay(tmp_path, [TS_930, TS_932])
        r.next()
        with pytest.raises(LookaheadGuardError, match="reset"):
            r.reset()

    def test_peek_next_raises(self, tmp_path):
        r = _replay(tmp_path, [TS_930, TS_932])
        with pytest.raises(LookaheadGuardError, match="peek"):
            r.peek_next()

    def test_goto_backward_raises(self, tmp_path):
        r = _replay(tmp_path, [TS_930, TS_932, TS_934])
        r.goto(TS_934)  # move forward
        with pytest.raises(LookaheadGuardError, match="forward"):
            r.goto(TS_930)  # backward — blocked

    def test_goto_backward_error_message_is_clear(self, tmp_path):
        r = _replay(tmp_path, [TS_930, TS_932])
        r.next()
        try:
            r.goto(TS_930)
            pytest.fail("Expected LookaheadGuardError")
        except LookaheadGuardError as e:
            assert "forward" in str(e).lower() or "before" in str(e).lower()


# ------------------------------------------------------------------
# Iteration
# ------------------------------------------------------------------

class TestIteration:
    def test_iterates_all_candles_including_last(self, tmp_path):
        r = _replay(tmp_path, [TS_930, TS_932, TS_934])
        seen = [c.timestamp for c in r]
        assert seen == [TS_930, TS_932, TS_934]

    def test_single_candle_iteration(self, tmp_path):
        r = _replay(tmp_path, [TS_930])
        seen = [c.timestamp for c in r]
        assert seen == [TS_930]

    def test_iteration_leaves_cursor_at_last(self, tmp_path):
        r = _replay(tmp_path, [TS_930, TS_932, TS_934])
        list(r)
        assert r.finished()
        assert r.current().timestamp == TS_934

    def test_iteration_from_mid_position(self, tmp_path):
        r = _replay(tmp_path, [TS_930, TS_932, TS_934])
        r.next()  # move to TS_932
        seen = [c.timestamp for c in r]
        assert seen == [TS_932, TS_934]


# ------------------------------------------------------------------
# Properties
# ------------------------------------------------------------------

class TestProperties:
    def test_symbol(self, tmp_path):
        r = _replay(tmp_path, [TS_930])
        assert r.symbol == "GENERIC"

    def test_timeframe(self, tmp_path):
        r = _replay(tmp_path, [TS_930])
        assert r.timeframe == "2"

    def test_total_candles(self, tmp_path):
        r = _replay(tmp_path, [TS_930, TS_932, TS_934])
        assert r.total_candles == 3

    def test_len(self, tmp_path):
        r = _replay(tmp_path, [TS_930, TS_932])
        assert len(r) == 2

    def test_repr(self, tmp_path):
        r = _replay(tmp_path, [TS_930, TS_932])
        assert "BacktestReplay" in repr(r)
        assert "day.jsonl" in repr(r)

    def test_source_path(self, tmp_path):
        path = tmp_path / "day.jsonl"
        _write_jsonl(path, [TS_930])
        r = BacktestReplay.from_path(path)
        assert r.source_path == path


# ------------------------------------------------------------------
# Factory
# ------------------------------------------------------------------

class TestFactory:
    def test_from_path_loads_engine(self, tmp_path):
        path = tmp_path / "day.jsonl"
        _write_jsonl(path, [TS_930, TS_932])
        r = BacktestReplay.from_path(path)
        assert r.total_candles == 2
        assert r.current().timestamp == TS_930


# ------------------------------------------------------------------
# Lookahead invariant
# ------------------------------------------------------------------

class TestLookaheadInvariant:
    def test_no_future_candle_accessible_via_current(self, tmp_path):
        r = _replay(tmp_path, [TS_930, TS_932, TS_934])
        # At cursor=0, current is TS_930; TS_932 and TS_934 are inaccessible
        assert r.current().timestamp == TS_930

    def test_next_only_reveals_one_candle_at_a_time(self, tmp_path):
        r = _replay(tmp_path, [TS_930, TS_932, TS_934])
        seen = set()
        seen.add(r.current().timestamp)
        r.next()
        seen.add(r.current().timestamp)
        # TS_934 has never been at cursor — not accessible
        assert TS_934 not in seen

    def test_no_trading_logic_in_source(self):
        import inspect
        from src.engine import backtest_replay as mod
        source = inspect.getsource(mod)
        forbidden = ["buy", "sell", "entry", "exit", "stop_loss",
                     "take_profit", "ltp", "rejection", "reversal", "bounce"]
        for term in forbidden:
            assert term not in source, f"Trading term {term!r} found in backtest_replay.py"

    def test_no_hardcoded_ticker(self):
        import inspect
        from src.engine import backtest_replay as mod
        source = inspect.getsource(mod)
        for ticker in ("TSLA", "AAPL", "SPY"):
            assert ticker not in source, f"Ticker {ticker!r} hardcoded in backtest_replay.py"
