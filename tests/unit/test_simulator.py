"""Unit tests for Phase 5B forward-only outcome simulation."""
from __future__ import annotations

from pathlib import Path

from src.collector.candle_record import build_record
from src.collector.candle_schema import CandleSnapshot
from src.collector.jsonl_store import JsonlStore
from src.engine.backtest_replay import BacktestReplay
from src.simulator.execution_contract import ExecutionOutcome
from src.simulator.simulator import OutcomeSimulator, simulate_trade_plan
from src.simulator.trade_plan import TradePlan, TradePlanDirection, PlanStatus


TS0 = 1705329000
STEP = 120


def _write_day(path: Path, candles: list[dict[str, float]]) -> Path:
    with JsonlStore(path) as store:
        for i, c in enumerate(candles):
            snap = CandleSnapshot(
                timestamp=TS0 + i * STEP,
                open=c["open"],
                high=c["high"],
                low=c["low"],
                close=c["close"],
                volume=1000.0 + i,
                symbol="TSLA",
                timeframe="2",
                replay_date="2024-01-15",
            )
            store.append(build_record(snap, {}, i))
    return path


def _replay(tmp_path: Path, candles: list[dict[str, float]]) -> BacktestReplay:
    return BacktestReplay.from_path(_write_day(tmp_path / "day.jsonl", candles))


def _plan(**overrides) -> TradePlan:
    base = dict(
        plan_id="TSLA_2024-01-15_00001",
        timestamp=TS0 + STEP,
        symbol="TSLA",
        timeframe="2",
        replay_date="2024-01-15",
        candle_index=1,
        setup_type="FAILED_LTP",
        watch_type="FAILED_LTP_WATCH",
        grade="B",
        source_candle_index=0,
        direction=TradePlanDirection.LONG,
        entry_trigger=100.0,
        stop=98.0,
        risk=2.0,
        target_1_5r=103.0,
        reward_risk=1.5,
        invalidation="Invalidated if price commits decisively in the opposite direction.",
        plan_status=PlanStatus.VALID,
        rejection_reason=None,
    )
    base.update(overrides)
    return TradePlan(**base)


class TestOutcomeSimulator:
    def test_valid_plan_resolves_as_target_hit(self, tmp_path):
        replay = _replay(tmp_path, [
            {"open": 99.0, "high": 101.0, "low": 98.5, "close": 100.0},
            {"open": 100.0, "high": 104.0, "low": 97.0, "close": 100.0},
            {"open": 100.5, "high": 103.5, "low": 99.5, "close": 103.0},
        ])
        result = simulate_trade_plan(_plan(), replay)
        assert result.outcome_status == ExecutionOutcome.TARGET_BEFORE_STOP
        assert result.exit_candle_index == 2
        assert result.exit_price == 103.0
        assert result.realized_r == 1.5

    def test_valid_plan_resolves_as_stop_hit(self, tmp_path):
        replay = _replay(tmp_path, [
            {"open": 99.0, "high": 101.0, "low": 98.5, "close": 100.0},
            {"open": 100.0, "high": 104.0, "low": 97.0, "close": 100.0},
            {"open": 99.5, "high": 101.0, "low": 97.5, "close": 98.0},
        ])
        result = simulate_trade_plan(_plan(), replay)
        assert result.outcome_status == ExecutionOutcome.STOP_BEFORE_TARGET
        assert result.exit_candle_index == 2
        assert result.exit_price == 98.0
        assert result.realized_r == -1.0

    def test_both_touched_same_candle_returns_ambiguous(self, tmp_path):
        replay = _replay(tmp_path, [
            {"open": 99.0, "high": 101.0, "low": 98.5, "close": 100.0},
            {"open": 100.0, "high": 104.0, "low": 97.0, "close": 100.0},
            {"open": 100.0, "high": 103.5, "low": 97.5, "close": 101.0},
        ])
        result = simulate_trade_plan(_plan(), replay)
        assert result.outcome_status == ExecutionOutcome.AMBIGUOUS_BOTH_TOUCHED
        assert result.exit_candle_index == 2
        assert result.exit_price is None
        assert result.realized_r is None

    def test_gap_beyond_target_handled_deterministically(self, tmp_path):
        replay = _replay(tmp_path, [
            {"open": 99.0, "high": 101.0, "low": 98.5, "close": 100.0},
            {"open": 100.0, "high": 104.0, "low": 97.0, "close": 100.0},
            {"open": 104.0, "high": 104.5, "low": 103.5, "close": 104.2},
        ])
        result = simulate_trade_plan(_plan(), replay)
        assert result.outcome_status == ExecutionOutcome.GAP_BEYOND_TARGET
        assert result.exit_candle_index == 2
        assert result.exit_price == 104.0
        assert result.realized_r == 1.5

    def test_gap_beyond_stop_handled_deterministically(self, tmp_path):
        replay = _replay(tmp_path, [
            {"open": 99.0, "high": 101.0, "low": 98.5, "close": 100.0},
            {"open": 100.0, "high": 104.0, "low": 97.0, "close": 100.0},
            {"open": 97.0, "high": 98.0, "low": 96.5, "close": 97.5},
        ])
        result = simulate_trade_plan(_plan(), replay)
        assert result.outcome_status == ExecutionOutcome.GAP_BEYOND_STOP
        assert result.exit_candle_index == 2
        assert result.exit_price == 97.0
        assert result.realized_r == -1.0

    def test_unresolved_at_end_handled_deterministically(self, tmp_path):
        replay = _replay(tmp_path, [
            {"open": 99.0, "high": 101.0, "low": 98.5, "close": 100.0},
            {"open": 100.0, "high": 104.0, "low": 97.0, "close": 100.0},
            {"open": 100.5, "high": 102.5, "low": 98.5, "close": 101.0},
            {"open": 101.0, "high": 102.0, "low": 99.0, "close": 101.5},
        ])
        result = simulate_trade_plan(_plan(), replay)
        assert result.outcome_status == ExecutionOutcome.UNRESOLVED_END_OF_REPLAY
        assert result.exit_candle_index == 3
        assert result.exit_price is None
        assert result.realized_r is None

    def test_rejected_plan_is_skipped(self, tmp_path):
        replay = _replay(tmp_path, [
            {"open": 99.0, "high": 101.0, "low": 98.5, "close": 100.0},
            {"open": 100.0, "high": 104.0, "low": 97.0, "close": 100.0},
            {"open": 104.0, "high": 104.5, "low": 103.5, "close": 104.2},
        ])
        result = simulate_trade_plan(
            _plan(
                plan_status=PlanStatus.REJECTED_NOT_TRADABLE,
                rejection_reason="not executable",
            ),
            replay,
        )
        assert result.outcome_status == ExecutionOutcome.SKIPPED_REJECTED_PLAN
        assert result.exit_candle_index is None
        assert replay.cursor == 0

    def test_same_eval_candle_cannot_close_trade(self, tmp_path):
        replay = _replay(tmp_path, [
            {"open": 99.0, "high": 101.0, "low": 98.5, "close": 100.0},
            {"open": 100.0, "high": 104.0, "low": 97.0, "close": 100.0},
            {"open": 99.5, "high": 101.0, "low": 97.5, "close": 98.0},
        ])
        result = simulate_trade_plan(_plan(), replay)
        assert result.outcome_status == ExecutionOutcome.STOP_BEFORE_TARGET
        assert result.exit_candle_index == 2
        assert all("evaluate candle_index=1" not in line for line in result.audit_trail)

    def test_simulator_starts_at_plan_candle_index_plus_one(self, tmp_path):
        replay = _replay(tmp_path, [
            {"open": 99.0, "high": 101.0, "low": 98.5, "close": 100.0},
            {"open": 100.0, "high": 104.0, "low": 97.0, "close": 100.0},
            {"open": 100.5, "high": 103.5, "low": 99.5, "close": 103.0},
        ])
        result = simulate_trade_plan(_plan(), replay)
        assert "first eligible outcome candle index=2" in result.audit_trail[1]
        assert replay.cursor == 2

    def test_repeat_run_gives_identical_result(self, tmp_path):
        candles = [
            {"open": 99.0, "high": 101.0, "low": 98.5, "close": 100.0},
            {"open": 100.0, "high": 104.0, "low": 97.0, "close": 100.0},
            {"open": 100.5, "high": 103.5, "low": 99.5, "close": 103.0},
        ]
        result_1 = simulate_trade_plan(_plan(), _replay(tmp_path / "a", candles))
        result_2 = simulate_trade_plan(_plan(), _replay(tmp_path / "b", candles))
        assert result_1.to_dict() == result_2.to_dict()

    def test_outcome_result_validates_cleanly(self, tmp_path):
        replay = _replay(tmp_path, [
            {"open": 99.0, "high": 101.0, "low": 98.5, "close": 100.0},
            {"open": 100.0, "high": 104.0, "low": 97.0, "close": 100.0},
            {"open": 100.5, "high": 103.5, "low": 99.5, "close": 103.0},
        ])
        result = OutcomeSimulator().simulate(_plan(), replay)
        assert result.validate() == []
