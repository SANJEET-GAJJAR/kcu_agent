"""Unit tests for PolicyReplay — dual-timeframe policy replay engine."""
from __future__ import annotations

import json
import pytest
from pathlib import Path

from src.collector.candle_schema import CandleSnapshot
from src.collector.candle_record import CandleRecord, build_record
from src.collector.chart_preflight import StaleCollectionError
from src.collector.jsonl_store import JsonlStore
from src.collector.timeframe_policy import TimeframePolicyConfig, TimeframeWindow
from src.engine.backtest_replay import LookaheadGuardError
from src.engine.replay_engine import EndOfReplay, TimestampNotFound
from src.engine.policy_replay import PolicyReplay, PolicyReplayError, _policy_boundary_ts

# ------------------------------------------------------------------
# Representative timestamps (2024-01-15, EST = UTC-5)
# ------------------------------------------------------------------
_DATE = "2024-01-15"

# 09:30 ET = 14:30 UTC = 1705329000
_TS_PRE1 = 1705329000   # 09:30 ET — pre-boundary (2m territory)
_TS_PRE2 = 1705330680   # 09:58 ET — pre-boundary (2m territory)

# 10:00 ET = 15:00 UTC = 1705330800 — policy boundary
_BOUNDARY = 1705330800

_TS_POST1 = 1705331100  # 10:05 ET — post-boundary (5m territory)
_TS_POST2 = 1705331400  # 10:10 ET — post-boundary (5m territory)
_TS_POST3 = 1705352400  # 16:00 ET — session close


# ------------------------------------------------------------------
# Minimal test policy (mirrors timeframe_policy.yaml)
# ------------------------------------------------------------------

def _test_policy() -> TimeframePolicyConfig:
    return TimeframePolicyConfig(
        version="1.0.0",
        policy_name="test",
        windows=[
            TimeframeWindow(start="09:30", end="10:00", timeframe="2", label="open_range"),
            TimeframeWindow(start="10:00", end="16:00", timeframe="5", label="main_session"),
        ],
        required_timeframes={"full_protocol": ["2", "5"], "smoke_test": ["2"]},
        allow_derived_timeframes=False,
    )


# ------------------------------------------------------------------
# Fixture helpers
# ------------------------------------------------------------------

def _snap(ts: int, timeframe: str = "2", symbol: str = "GENERIC") -> CandleSnapshot:
    return CandleSnapshot(
        timestamp=ts, open=195.0, high=196.5, low=194.0, close=196.0,
        volume=10000.0, symbol=symbol, timeframe=timeframe, replay_date=_DATE,
    )


def _write_jsonl(path: Path, timestamps: list[int], timeframe: str = "2") -> Path:
    with JsonlStore(path) as store:
        for i, ts in enumerate(timestamps):
            store.append(build_record(_snap(ts, timeframe=timeframe), {}, i))
    return path


def _write_preflight(path: Path, passed: bool = True) -> None:
    companion = path.with_name(path.stem + "_preflight.json")
    companion.write_text(json.dumps({"preflight_passed": passed}))


def _pair(
    tmp_path: Path,
    ts_2m: list[int],
    ts_5m: list[int],
    policy: TimeframePolicyConfig | None = None,
) -> PolicyReplay:
    p2 = tmp_path / "day_2m.jsonl"
    p5 = tmp_path / "day_5m.jsonl"
    _write_jsonl(p2, ts_2m, timeframe="2")
    _write_jsonl(p5, ts_5m, timeframe="5")
    return PolicyReplay.from_paths(p2, p5, _DATE, policy or _test_policy())


# ------------------------------------------------------------------
# Boundary helper
# ------------------------------------------------------------------

class TestPolicyBoundaryTs:
    def test_boundary_is_10am_et(self):
        policy = _test_policy()
        boundary = _policy_boundary_ts(_DATE, policy)
        assert boundary == _BOUNDARY

    def test_no_5m_window_raises(self):
        policy = TimeframePolicyConfig(
            version="1.0.0",
            policy_name="no5m",
            windows=[TimeframeWindow(start="09:30", end="16:00", timeframe="2", label="all")],
            required_timeframes={"smoke_test": ["2"]},
            allow_derived_timeframes=False,
        )
        with pytest.raises(PolicyReplayError, match="5m window"):
            _policy_boundary_ts(_DATE, policy)


# ------------------------------------------------------------------
# Build / merge logic
# ------------------------------------------------------------------

class TestPolicyReplayBuild:
    def test_pre_boundary_candles_are_2m(self, tmp_path):
        r = _pair(tmp_path, [_TS_PRE1, _TS_PRE2], [_TS_POST1, _TS_POST2])
        pre = [c for c in r._candles if c.timestamp < _BOUNDARY]
        assert all(c.snapshot.timeframe == "2" for c in pre)

    def test_post_boundary_candles_are_5m(self, tmp_path):
        r = _pair(tmp_path, [_TS_PRE1, _TS_PRE2], [_TS_POST1, _TS_POST2])
        post = [c for c in r._candles if c.timestamp >= _BOUNDARY]
        assert all(c.snapshot.timeframe == "5" for c in post)

    def test_merged_sequence_is_sorted(self, tmp_path):
        r = _pair(tmp_path, [_TS_PRE1, _TS_PRE2], [_TS_POST1, _TS_POST2])
        ts = [c.timestamp for c in r._candles]
        assert ts == sorted(ts)

    def test_total_candle_count_correct(self, tmp_path):
        r = _pair(tmp_path, [_TS_PRE1, _TS_PRE2], [_TS_POST1, _TS_POST2])
        assert r.total_candles == 4

    def test_5m_candle_exactly_at_boundary_included(self, tmp_path):
        # A 5m candle whose ts == _BOUNDARY must be in the post-boundary section
        r = _pair(tmp_path, [_TS_PRE1], [_BOUNDARY, _TS_POST1])
        post = [c for c in r._candles if c.timestamp >= _BOUNDARY]
        assert any(c.timestamp == _BOUNDARY for c in post)
        assert all(c.snapshot.timeframe == "5" for c in post)

    def test_2m_candle_exactly_at_boundary_excluded(self, tmp_path):
        # A 2m candle whose ts == _BOUNDARY must NOT be included (it belongs to 5m window)
        r = _pair(tmp_path, [_TS_PRE1, _BOUNDARY], [_BOUNDARY, _TS_POST1])
        candle_at_boundary = next(
            (c for c in r._candles if c.timestamp == _BOUNDARY), None
        )
        assert candle_at_boundary is not None
        assert candle_at_boundary.snapshot.timeframe == "5"

    def test_duplicate_timestamps_deduplicated(self, tmp_path):
        # If both files have a candle at the same ts, keep only one
        # (2m takes priority when both are pre-boundary; 5m takes priority post-boundary)
        p2 = tmp_path / "dup_2m.jsonl"
        p5 = tmp_path / "dup_5m.jsonl"
        _write_jsonl(p2, [_TS_PRE1, _TS_PRE1], timeframe="2")
        _write_jsonl(p5, [_TS_POST1, _TS_POST1], timeframe="5")
        r = PolicyReplay.from_paths(p2, p5, _DATE, _test_policy())
        assert r.total_candles == 2

    def test_empty_pre_boundary_uses_post_only(self, tmp_path):
        # 2m file has all candles after the boundary → pre_boundary is empty
        # post_boundary has content → should still build
        r = _pair(tmp_path, [_BOUNDARY + 60], [_TS_POST1, _TS_POST2])
        # The 2m candle at _BOUNDARY+60 is excluded (>= boundary → excluded from pre)
        # The 5m candles are included
        assert r.total_candles == 2

    def test_missing_2m_file_raises(self, tmp_path):
        p2 = tmp_path / "missing_2m.jsonl"
        p5 = tmp_path / "day_5m.jsonl"
        _write_jsonl(p5, [_TS_POST1], timeframe="5")
        with pytest.raises(PolicyReplayError, match="not found"):
            PolicyReplay.from_paths(p2, p5, _DATE, _test_policy())

    def test_missing_5m_file_raises(self, tmp_path):
        p2 = tmp_path / "day_2m.jsonl"
        p5 = tmp_path / "missing_5m.jsonl"
        _write_jsonl(p2, [_TS_PRE1], timeframe="2")
        with pytest.raises(PolicyReplayError, match="not found"):
            PolicyReplay.from_paths(p2, p5, _DATE, _test_policy())

    def test_empty_2m_file_raises(self, tmp_path):
        p2 = tmp_path / "empty_2m.jsonl"
        p5 = tmp_path / "day_5m.jsonl"
        p2.touch()
        _write_jsonl(p5, [_TS_POST1], timeframe="5")
        with pytest.raises(PolicyReplayError, match="empty"):
            PolicyReplay.from_paths(p2, p5, _DATE, _test_policy())


# ------------------------------------------------------------------
# Navigation
# ------------------------------------------------------------------

class TestNavigation:
    def _r(self, tmp_path: Path) -> PolicyReplay:
        return _pair(tmp_path, [_TS_PRE1, _TS_PRE2], [_TS_POST1, _TS_POST2])

    def test_current_returns_first_candle(self, tmp_path):
        r = self._r(tmp_path)
        assert r.current().timestamp == _TS_PRE1

    def test_next_advances_cursor(self, tmp_path):
        r = self._r(tmp_path)
        c = r.next()
        assert c.timestamp == _TS_PRE2
        assert r.cursor == 1

    def test_next_at_last_raises_end_of_replay(self, tmp_path):
        r = _pair(tmp_path, [_TS_PRE1], [_TS_POST1])
        r.next()  # now at _TS_POST1
        with pytest.raises(EndOfReplay):
            r.next()

    def test_finished_false_at_start(self, tmp_path):
        r = self._r(tmp_path)
        assert r.finished() is False

    def test_finished_true_at_last(self, tmp_path):
        r = _pair(tmp_path, [_TS_PRE1], [_TS_POST1])
        r.next()
        assert r.finished() is True

    def test_at_beginning_true_initially(self, tmp_path):
        r = self._r(tmp_path)
        assert r.at_beginning() is True

    def test_at_beginning_false_after_next(self, tmp_path):
        r = self._r(tmp_path)
        r.next()
        assert r.at_beginning() is False

    def test_goto_forward_permitted(self, tmp_path):
        r = self._r(tmp_path)
        c = r.goto(_TS_POST1)
        assert c.timestamp == _TS_POST1

    def test_goto_same_timestamp_permitted(self, tmp_path):
        r = self._r(tmp_path)
        c = r.goto(_TS_PRE1)
        assert c.timestamp == _TS_PRE1

    def test_goto_nonexistent_ts_raises(self, tmp_path):
        r = self._r(tmp_path)
        nonexistent = _TS_POST2 + 9999  # larger than all candles, not in sequence
        with pytest.raises(TimestampNotFound):
            r.goto(nonexistent)

    def test_full_walk_visits_all_candles(self, tmp_path):
        r = self._r(tmp_path)
        seen = []
        seen.append(r.current().timestamp)
        while not r.finished():
            seen.append(r.next().timestamp)
        assert seen == [_TS_PRE1, _TS_PRE2, _TS_POST1, _TS_POST2]


# ------------------------------------------------------------------
# Blocked operations
# ------------------------------------------------------------------

class TestBlockedOperations:
    def _r(self, tmp_path: Path) -> PolicyReplay:
        return _pair(tmp_path, [_TS_PRE1, _TS_PRE2], [_TS_POST1])

    def test_previous_raises(self, tmp_path):
        r = self._r(tmp_path)
        r.next()
        with pytest.raises(LookaheadGuardError, match="previous"):
            r.previous()

    def test_previous_raises_even_at_start(self, tmp_path):
        r = self._r(tmp_path)
        with pytest.raises(LookaheadGuardError):
            r.previous()

    def test_reset_raises(self, tmp_path):
        r = self._r(tmp_path)
        r.next()
        with pytest.raises(LookaheadGuardError, match="reset"):
            r.reset()

    def test_peek_next_raises(self, tmp_path):
        r = self._r(tmp_path)
        with pytest.raises(LookaheadGuardError, match="peek"):
            r.peek_next()

    def test_goto_backward_raises(self, tmp_path):
        r = self._r(tmp_path)
        r.goto(_TS_PRE2)
        with pytest.raises(LookaheadGuardError, match="forward"):
            r.goto(_TS_PRE1)


# ------------------------------------------------------------------
# Preflight enforcement
# ------------------------------------------------------------------

class TestPreflightEnforcement:
    def test_from_validated_paths_requires_preflight(self, tmp_path):
        p2 = tmp_path / "day_2m.jsonl"
        p5 = tmp_path / "day_5m.jsonl"
        _write_jsonl(p2, [_TS_PRE1], timeframe="2")
        _write_jsonl(p5, [_TS_POST1], timeframe="5")
        # No companion files written → should raise StaleCollectionError
        with pytest.raises(StaleCollectionError):
            PolicyReplay.from_validated_paths(p2, p5, _DATE, _test_policy())

    def test_from_validated_paths_fails_with_failed_preflight(self, tmp_path):
        p2 = tmp_path / "day_2m.jsonl"
        p5 = tmp_path / "day_5m.jsonl"
        _write_jsonl(p2, [_TS_PRE1], timeframe="2")
        _write_jsonl(p5, [_TS_POST1], timeframe="5")
        _write_preflight(p2, passed=True)
        _write_preflight(p5, passed=False)  # 5m preflight failed
        with pytest.raises(StaleCollectionError):
            PolicyReplay.from_validated_paths(p2, p5, _DATE, _test_policy())

    def test_from_validated_paths_succeeds_with_valid_preflight(self, tmp_path):
        p2 = tmp_path / "day_2m.jsonl"
        p5 = tmp_path / "day_5m.jsonl"
        _write_jsonl(p2, [_TS_PRE1], timeframe="2")
        _write_jsonl(p5, [_TS_POST1], timeframe="5")
        _write_preflight(p2, passed=True)
        _write_preflight(p5, passed=True)
        r = PolicyReplay.from_validated_paths(p2, p5, _DATE, _test_policy())
        assert r.total_candles == 2

    def test_from_paths_skips_preflight(self, tmp_path):
        # from_paths does not check preflight — no companion files needed
        p2 = tmp_path / "day_2m.jsonl"
        p5 = tmp_path / "day_5m.jsonl"
        _write_jsonl(p2, [_TS_PRE1], timeframe="2")
        _write_jsonl(p5, [_TS_POST1], timeframe="5")
        r = PolicyReplay.from_paths(p2, p5, _DATE, _test_policy())
        assert r.total_candles == 2


# ------------------------------------------------------------------
# Protocol gate (from_protocol)
# ------------------------------------------------------------------

class TestProtocolGate:
    def _write_protocol_pair(
        self,
        tmp_path: Path,
        passed_2m: bool = True,
        passed_5m: bool = True,
        has_2m: bool = True,
        has_5m: bool = True,
    ) -> tuple[Path, str]:
        output_dir = tmp_path / "candles"
        output_dir.mkdir()
        if has_2m:
            p2 = output_dir / "TSLA_2024-01-15_2m.jsonl"
            _write_jsonl(p2, [_TS_PRE1], timeframe="2")
            if passed_2m:
                _write_preflight(p2, passed=True)
        if has_5m:
            p5 = output_dir / "TSLA_2024-01-15_5m.jsonl"
            _write_jsonl(p5, [_TS_POST1], timeframe="5")
            if passed_5m:
                _write_preflight(p5, passed=True)
        return output_dir, _DATE

    def test_from_protocol_valid_pair_builds_replay(self, tmp_path):
        from src.collector.timeframe_policy import load_timeframe_policy
        output_dir, date = self._write_protocol_pair(tmp_path)
        r = PolicyReplay.from_protocol("TSLA", date, output_dir, _test_policy())
        assert r.total_candles == 2

    def test_from_protocol_missing_5m_raises(self, tmp_path):
        from src.collector.timeframe_policy import ProtocolReadinessError
        output_dir, date = self._write_protocol_pair(tmp_path, has_5m=False)
        with pytest.raises(ProtocolReadinessError):
            PolicyReplay.from_protocol("TSLA", date, output_dir, _test_policy())

    def test_from_protocol_missing_2m_raises(self, tmp_path):
        from src.collector.timeframe_policy import ProtocolReadinessError
        output_dir, date = self._write_protocol_pair(tmp_path, has_2m=False)
        with pytest.raises(ProtocolReadinessError):
            PolicyReplay.from_protocol("TSLA", date, output_dir, _test_policy())

    def test_from_protocol_failed_5m_preflight_raises(self, tmp_path):
        from src.collector.timeframe_policy import ProtocolReadinessError
        output_dir, date = self._write_protocol_pair(tmp_path, passed_5m=False)
        with pytest.raises(ProtocolReadinessError):
            PolicyReplay.from_protocol("TSLA", date, output_dir, _test_policy())


# ------------------------------------------------------------------
# State and properties
# ------------------------------------------------------------------

class TestStateAndProperties:
    def test_state_returns_replay_state(self, tmp_path):
        r = _pair(tmp_path, [_TS_PRE1], [_TS_POST1])
        s = r.state()
        assert s.cursor == 0
        assert s.current_timestamp == _TS_PRE1
        assert s.total_candles == 2

    def test_state_source_path_includes_both_files(self, tmp_path):
        r = _pair(tmp_path, [_TS_PRE1], [_TS_POST1])
        s = r.state()
        assert "2m" in s.source_path
        assert "5m" in s.source_path

    def test_state_timeframe_reflects_current_candle(self, tmp_path):
        r = _pair(tmp_path, [_TS_PRE1], [_TS_POST1])
        assert r.state().timeframe == "2"   # cursor on pre-boundary 2m candle
        r.next()
        assert r.state().timeframe == "5"   # cursor on post-boundary 5m candle

    def test_total_candles_property(self, tmp_path):
        r = _pair(tmp_path, [_TS_PRE1, _TS_PRE2], [_TS_POST1])
        assert r.total_candles == 3

    def test_len(self, tmp_path):
        r = _pair(tmp_path, [_TS_PRE1, _TS_PRE2], [_TS_POST1])
        assert len(r) == 3

    def test_date_property(self, tmp_path):
        r = _pair(tmp_path, [_TS_PRE1], [_TS_POST1])
        assert r.date == _DATE

    def test_repr_contains_source_and_position(self, tmp_path):
        r = _pair(tmp_path, [_TS_PRE1], [_TS_POST1])
        rep = repr(r)
        assert "PolicyReplay" in rep


# ------------------------------------------------------------------
# Iteration
# ------------------------------------------------------------------

class TestIteration:
    def test_iterates_all_candles_including_last(self, tmp_path):
        r = _pair(tmp_path, [_TS_PRE1, _TS_PRE2], [_TS_POST1])
        seen = [c.timestamp for c in r]
        assert seen == [_TS_PRE1, _TS_PRE2, _TS_POST1]

    def test_single_candle_iteration(self, tmp_path):
        r = _pair(tmp_path, [_TS_PRE1], [_TS_POST1])
        r.next()  # move to post-boundary
        # iterate from current position
        seen = [c.timestamp for c in r]
        assert seen == [_TS_POST1]

    def test_iteration_leaves_cursor_at_last(self, tmp_path):
        r = _pair(tmp_path, [_TS_PRE1, _TS_PRE2], [_TS_POST1])
        list(r)
        assert r.finished()
        assert r.current().timestamp == _TS_POST1


# ------------------------------------------------------------------
# Lookahead invariant
# ------------------------------------------------------------------

class TestLookaheadInvariant:
    def test_current_only_reveals_cursor_position(self, tmp_path):
        r = _pair(tmp_path, [_TS_PRE1, _TS_PRE2], [_TS_POST1])
        assert r.current().timestamp == _TS_PRE1
        # _TS_PRE2 and _TS_POST1 are not accessible at cursor=0

    def test_next_reveals_one_candle_at_a_time(self, tmp_path):
        r = _pair(tmp_path, [_TS_PRE1, _TS_PRE2], [_TS_POST1])
        seen = {r.current().timestamp}
        r.next()
        seen.add(r.current().timestamp)
        assert _TS_POST1 not in seen


# ------------------------------------------------------------------
# No trading logic, no hardcoded tickers
# ------------------------------------------------------------------

class TestSourceIntegrity:
    def test_no_trading_terms_in_source(self):
        import inspect
        from src.engine import policy_replay as mod
        source = inspect.getsource(mod)
        forbidden = [
            "buy", "sell", "entry", "exit", "stop_loss",
            "take_profit", "ltp", "rejection", "reversal", "bounce",
        ]
        for term in forbidden:
            assert term not in source, (
                f"Trading logic term {term!r} found in policy_replay.py"
            )

    def test_no_hardcoded_tickers_in_source(self):
        import inspect
        from src.engine import policy_replay as mod
        source = inspect.getsource(mod)
        for ticker in ("TSLA", "AAPL", "SPY", "ES1!"):
            assert ticker not in source, (
                f"Hardcoded ticker {ticker!r} found in policy_replay.py"
            )
