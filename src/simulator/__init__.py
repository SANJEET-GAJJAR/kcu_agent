"""Simulation-phase contracts and helpers."""

from .day_runner import (
    DayRunArtifacts,
    DayRunResult,
    DayRunner,
    run_day_from_confirmations_path,
    run_day_from_trade_plans_path,
)
from .execution_contract import (
    CandleExecutionView,
    ExecutionDecision,
    ExecutionOutcome,
    can_scan_outcome_on_candle,
    outcome_scan_start_candle_index,
    resolve_candle_outcome,
    skip_rejected_plan,
    unresolved_at_end_of_replay,
)
from .outcome import OutcomeResult
from .simulator import OutcomeSimulationError, OutcomeSimulator, simulate_trade_plan

__all__ = [
    "CandleExecutionView",
    "DayRunArtifacts",
    "DayRunResult",
    "DayRunner",
    "ExecutionDecision",
    "ExecutionOutcome",
    "OutcomeResult",
    "OutcomeSimulationError",
    "OutcomeSimulator",
    "can_scan_outcome_on_candle",
    "outcome_scan_start_candle_index",
    "resolve_candle_outcome",
    "run_day_from_confirmations_path",
    "run_day_from_trade_plans_path",
    "simulate_trade_plan",
    "skip_rejected_plan",
    "unresolved_at_end_of_replay",
]
