"""Forward-only deterministic outcome simulator for Phase 5B."""
from __future__ import annotations

from dataclasses import dataclass

from src.collector.candle_record import CandleRecord
from src.engine.backtest_replay import BacktestReplay
from src.simulator.execution_contract import (
    CandleExecutionView,
    ExecutionDecision,
    ExecutionOutcome,
    outcome_scan_start_candle_index,
    resolve_candle_outcome,
    skip_rejected_plan,
    unresolved_at_end_of_replay,
)
from src.simulator.outcome import OutcomeResult
from src.simulator.trade_plan import TradePlan


class OutcomeSimulationError(Exception):
    """Raised when replay state cannot safely simulate the requested plan."""


@dataclass
class OutcomeSimulator:
    """Simulates one TradePlan using forward-only replay candles.

    This runner never infers execution semantics itself. All terminal decision
    logic is delegated to `execution_contract.py`.
    """

    def simulate(
        self,
        plan: TradePlan,
        replay: BacktestReplay,
    ) -> OutcomeResult:
        """Simulate one TradePlan to a terminal OutcomeResult."""
        if not plan.is_valid():
            decision = skip_rejected_plan(plan)
            return _result_for_skipped(plan, decision)

        audit: list[str] = [
            f"simulation started for plan_id={plan.plan_id}",
            f"first eligible outcome candle index={outcome_scan_start_candle_index(plan)}",
        ]

        current = replay.current()
        current_idx = _record_candle_index(current)
        start_idx = outcome_scan_start_candle_index(plan)

        audit.append(f"initial replay cursor candle_index={current_idx}")

        if current_idx > start_idx:
            raise OutcomeSimulationError(
                f"Replay cursor already past first eligible scan candle "
                f"(cursor={current_idx}, start={start_idx})"
            )

        while current_idx < start_idx:
            audit.append(
                f"advance replay from candle_index={current_idx} toward start={start_idx}"
            )
            if replay.finished():
                audit.append(
                    "replay ended before reaching first eligible outcome candle"
                )
                decision = unresolved_at_end_of_replay(plan)
                return _result_from_decision(plan, decision, current, audit)
            current = replay.next()
            current_idx = _record_candle_index(current)

        while True:
            view = CandleExecutionView(
                candle_index=current_idx,
                open=current.snapshot.open,
                high=current.snapshot.high,
                low=current.snapshot.low,
            )
            audit.append(
                f"evaluate candle_index={current_idx} "
                f"(open={view.open}, high={view.high}, low={view.low})"
            )

            decision = resolve_candle_outcome(plan, view)
            if decision is not None:
                audit.append(f"terminal decision={decision.outcome}")
                return _result_from_decision(plan, decision, current, audit)

            audit.append("no terminal outcome on this candle")
            if replay.finished():
                audit.append("replay ended without terminal candle resolution")
                decision = unresolved_at_end_of_replay(plan)
                return _result_from_decision(plan, decision, current, audit)

            current = replay.next()
            current_idx = _record_candle_index(current)


def simulate_trade_plan(
    plan: TradePlan,
    replay: BacktestReplay,
) -> OutcomeResult:
    """Convenience wrapper for one-shot simulation."""
    return OutcomeSimulator().simulate(plan, replay)


def _record_candle_index(record: CandleRecord) -> int:
    """Return deterministic candle_index from collection metadata."""
    if "candle_index" not in record.meta:
        raise OutcomeSimulationError(
            "Replay candle record is missing meta['candle_index']; "
            "cannot enforce phase 5B scan start deterministically."
        )
    return int(record.meta["candle_index"])


def _result_for_skipped(
    plan: TradePlan,
    decision: ExecutionDecision,
) -> OutcomeResult:
    audit = [
        f"plan_id={plan.plan_id} skipped before replay scan",
        decision.reason,
    ]
    return OutcomeResult(
        plan_id=plan.plan_id,
        symbol=plan.symbol,
        timeframe=plan.timeframe,
        replay_date=plan.replay_date,
        entry_candle_index=plan.candle_index,
        entry_timestamp=plan.timestamp,
        exit_candle_index=None,
        exit_timestamp=None,
        exit_price=None,
        exit_reason=decision.reason,
        realized_r=decision.realized_r,
        outcome_status=decision.outcome,
        counts_as_win=decision.counts_as_win,
        counts_as_loss=decision.counts_as_loss,
        audit_trail=audit,
    )


def _result_from_decision(
    plan: TradePlan,
    decision: ExecutionDecision,
    record: CandleRecord,
    audit: list[str],
) -> OutcomeResult:
    """Materialize a terminal ExecutionDecision into an OutcomeResult."""
    exit_idx = _record_candle_index(record)
    exit_ts = record.timestamp

    if decision.outcome == ExecutionOutcome.TARGET_BEFORE_STOP:
        exit_price = plan.target_1_5r
    elif decision.outcome == ExecutionOutcome.STOP_BEFORE_TARGET:
        exit_price = plan.stop
    elif decision.outcome in (
        ExecutionOutcome.GAP_BEYOND_TARGET,
        ExecutionOutcome.GAP_BEYOND_STOP,
    ):
        exit_price = record.snapshot.open
    elif decision.outcome == ExecutionOutcome.SKIPPED_REJECTED_PLAN:
        exit_idx = None
        exit_ts = None
        exit_price = None
    else:
        exit_price = None

    return OutcomeResult(
        plan_id=plan.plan_id,
        symbol=plan.symbol,
        timeframe=plan.timeframe,
        replay_date=plan.replay_date,
        entry_candle_index=plan.candle_index,
        entry_timestamp=plan.timestamp,
        exit_candle_index=exit_idx,
        exit_timestamp=exit_ts,
        exit_price=exit_price,
        exit_reason=decision.reason,
        realized_r=decision.realized_r,
        outcome_status=decision.outcome,
        counts_as_win=decision.counts_as_win,
        counts_as_loss=decision.counts_as_loss,
        audit_trail=list(audit),
    )
